"""Deluge HTTP connection and OAuth2 worker tests, no external network access."""
import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from app.deluge_http import send_deluge_http


class FakeResponse:
    def __init__(self, data, status=200):
        self.data, self.status = data, status
    def read(self, size):
        return self.data[:size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


def setup_connection(monkeypatch, auth_type="None"):
    connection = {"enabled": True, "url": "https://api.partner.example.com/hooks",
                  "methods": ["POST"], "auth_type": auth_type}
    if auth_type == "OAuth2":
        connection.update({
            "token_url":"https://auth.partner.example.com/token",
            "refresh_token_env":"TEST_REFRESH_TOKEN",
            "client_id_env":"TEST_CLIENT_ID",
            "client_secret_env":"TEST_CLIENT_SECRET",
        })
        monkeypatch.setenv("TEST_REFRESH_TOKEN", "refresh-test-only")
        monkeypatch.setenv("TEST_CLIENT_ID", "client-test-only")
        monkeypatch.setenv("TEST_CLIENT_SECRET", "secret-test-only")
    monkeypatch.setenv("DELUGE_HTTP_CONNECTIONS_JSON", json.dumps({"partner": connection}))
    return {"type":"deluge_http", "url":connection["url"], "connection":"partner",
            "method":"POST", "body":{"name":"Test"}}


def test_connection_scoped_http_request_is_bounded(monkeypatch):
    action = setup_connection(monkeypatch)
    seen = []
    class FakeOpener:
        def open(self, request, timeout):
            seen.append((request.full_url, request.get_method(), request.data,
                         request.get_header("X-crm-idempotency-key"), timeout))
            return FakeResponse(b"accepted", 202)
    with patch("app.deluge_http.build_opener", return_value=FakeOpener()):
        result = send_deluge_http(action, SimpleNamespace(idempotency_key="demo-key"))
    assert result == {"status": "delivered", "bytes": 8}
    assert seen[0][0] == "https://api.partner.example.com/hooks"
    assert seen[0][1] == "POST"
    assert json.loads(seen[0][2]) == {"name":"Test"}
    assert seen[0][3] == "demo-key"
    assert seen[0][4] == 12


def test_oauth2_refresh_connection_injects_bearer_token(monkeypatch):
    action = setup_connection(monkeypatch, "OAuth2")
    seen = []
    class FakeOpener:
        def open(self, request, timeout):
            seen.append(request)
            if "/token" in request.full_url:
                assert b"grant_type=refresh_token" in request.data
                return FakeResponse(b'{"access_token":"test-oauth-access-token"}')
            assert request.get_header("Authorization") == "Bearer test-oauth-access-token"
            return FakeResponse(b"ok")
    with patch("app.deluge_http.build_opener", return_value=FakeOpener()):
        assert send_deluge_http(action, SimpleNamespace(idempotency_key="oauth-key"))["status"] == "delivered"
    assert len(seen) == 2


@pytest.mark.parametrize("change", [
    {"url":"https://attacker.example.com/token"},
    {"url":"http://127.0.0.1/private"},
    {"url":"https://127.0.0.1/private"},
    {"headers":{"Authorization":"Bearer malicious"}},
    {"headers":{"X-Test":"injected\nline"}},
    {"method":"DELETE"},
])
def test_deluge_http_fails_closed(monkeypatch, change):
    action = setup_connection(monkeypatch)
    action.update(change)
    with pytest.raises(ValueError):
        send_deluge_http(action, SimpleNamespace(idempotency_key="test"))


def test_connection_secrets_are_not_from_script_headers(monkeypatch):
    action = setup_connection(monkeypatch)
    action["headers"] = {"Cookie":"example"}
    with pytest.raises(ValueError):
        send_deluge_http(action, SimpleNamespace(idempotency_key="test"))


def test_oauth2_client_credentials_grant(monkeypatch):
    action = setup_connection(monkeypatch, "OAuth2")
    config = json.loads(__import__("os").environ["DELUGE_HTTP_CONNECTIONS_JSON"])
    config["partner"].pop("refresh_token_env")
    config["partner"]["grant_type"] = "client_credentials"
    config["partner"]["scope"] = "records.write"
    monkeypatch.setenv("DELUGE_HTTP_CONNECTIONS_JSON", json.dumps(config))
    requests = []
    class FakeOpener:
        def open(self, request, timeout):
            requests.append(request)
            if "/token" in request.full_url:
                assert b"grant_type=client_credentials" in request.data
                assert b"scope=records.write" in request.data
                return FakeResponse(b'{"access_token":"client-credentials-test-token"}')
            assert request.get_header("Authorization") == "Bearer client-credentials-test-token"
            return FakeResponse(b"ok")
    with patch("app.deluge_http.build_opener", return_value=FakeOpener()):
        assert send_deluge_http(action, SimpleNamespace(idempotency_key="client-grant"))["status"] == "delivered"
    assert len(requests) == 2
