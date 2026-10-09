"""Connection-scoped outbound Deluge HTTP delivery, performed only by the worker.

Connections are provisioned in DELUGE_HTTP_CONNECTIONS_JSON and reference secrets
by environment-variable NAME, never by cleartext values in CRM records.
The script cannot choose a different destination from its connection.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,119}$")
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
MAX_PAYLOAD_BYTES = 32768
MAX_RESPONSE_BYTES = 131072


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        return None


def _safe_https(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Connection URL is missing or invalid")
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or
        parsed.username or parsed.password or parsed.fragment or
        parsed.port not in {None, 443}):
        raise ValueError("Connection must use a trusted HTTPS endpoint")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if parsed.hostname in {"localhost", "localhost.localdomain"} or "." not in parsed.hostname:
            raise ValueError("Local connection destinations are forbidden")
    else:
        raise ValueError("Literal IP connection destinations are forbidden")
    return url


def _env_secret(reference):
    if not isinstance(reference, str) or not ENV_NAME.fullmatch(reference):
        raise ValueError("Connection secret must use an environment-variable reference")
    value = os.environ.get(reference)
    if not value:
        raise ValueError("Connection secret has not been configured")
    return value


def _connection(name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("Connection name must be a safe identifier")
    try:
        raw = json.loads(os.getenv("DELUGE_HTTP_CONNECTIONS_JSON", "{}"))
    except (ValueError, TypeError) as error:
        raise ValueError("Server connection catalog is invalid") from error
    if not isinstance(raw, dict) or len(raw) > 100:
        raise ValueError("Server connection catalog is invalid")
    spec = raw.get(name)
    if not isinstance(spec, dict) or spec.get("enabled") is not True:
        raise ValueError("Connection is not enabled for Deluge execution")
    _safe_https(spec.get("url"))
    methods = spec.get("methods", ["GET"])
    if not isinstance(methods, list) or not methods or set(methods) - ALLOWED_METHODS:
        raise ValueError("Invalid connection method allowlist")
    return spec


def _oauth_token(spec):
    static = spec.get("access_token_env")
    if static:
        return _env_secret(static)
    if spec.get("auth_type") != "OAuth2":
        raise ValueError("OAuth2 connection not configured")
    # Supported grant: refresh_token. Initial interactive OAuth consent happens
    # outside the worker, and is not simulated by a fake callback.
    token_url = _safe_https(spec.get("token_url"))
    grant = spec.get("grant_type", "refresh_token")
    if grant not in {"refresh_token", "client_credentials"}:
        raise ValueError("Unsupported OAuth2 grant")
    fields = {
        "grant_type": grant,
        "client_id": _env_secret(spec.get("client_id_env")),
        "client_secret": _env_secret(spec.get("client_secret_env")),
    }
    if grant == "refresh_token":
        fields["refresh_token"] = _env_secret(spec.get("refresh_token_env"))
    if grant == "client_credentials" and spec.get("scope"):
        if not isinstance(spec["scope"], str) or len(spec["scope"]) > 1024:
            raise ValueError("Invalid OAuth2 connection scope")
        fields["scope"] = spec["scope"]
    request = Request(token_url, data=urlencode(fields).encode(), method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        raw = response.read(16385)
        if len(raw) > 16384 or response.status not in {200, 201}:
            raise ValueError("OAuth2 token request failed")
    try:
        token = json.loads(raw).get("access_token")
    except (ValueError, AttributeError) as error:
        raise ValueError("OAuth2 token response was not valid JSON") from error
    if not isinstance(token, str) or not 5 <= len(token) <= 8192:
        raise ValueError("OAuth2 provider did not return an access token")
    return token


def send_deluge_http(action, execution):
    """Deliver a queued request. Never return response data to a workflow variable."""
    if action.get("type") != "deluge_http":
        raise ValueError("Invalid Deluge HTTP action")
    spec = _connection(action.get("connection"))
    requested = _safe_https(action.get("url"))
    if requested != spec["url"]:
        raise ValueError("Request URL is not allowed by this connection")
    method = action.get("method", "GET")
    if method not in spec.get("methods", ["GET"]) or method not in ALLOWED_METHODS:
        raise ValueError("Request method is not allowed")
    headers = action.get("headers") or {}
    if not isinstance(headers, dict) or len(headers) > 20:
        raise ValueError("Invalid request headers")
    clean_headers = {"X-CRM-Idempotency-Key": str(execution.idempotency_key)}
    for key, value in headers.items():
        if (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,80}", key)
            or key.lower() in {"authorization", "host", "cookie", "proxy-authorization",
                               "connection", "transfer-encoding", "content-length"}
            or not isinstance(value, str) or len(value) > 1000 or
            "\n" in value or "\r" in value):
            raise ValueError("Forbidden Deluge HTTP header")
        clean_headers[key] = value
    auth_type = spec.get("auth_type", "None")
    if auth_type == "OAuth2":
        clean_headers["Authorization"] = "Bearer " + _oauth_token(spec)
    elif auth_type == "APIKey":
        header = spec.get("api_key_header", "X-API-Key")
        if not isinstance(header, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,80}", header):
            raise ValueError("Invalid API key header configuration")
        clean_headers[header] = _env_secret(spec.get("api_key_env"))
    elif auth_type != "None":
        raise ValueError("Unsupported connection authentication type")
    body = action.get("body")
    if body is not None and method == "GET":
        raise ValueError("GET request cannot send a body")
    if body is None:
        payload = None
    elif isinstance(body, (dict, list)):
        payload = json.dumps(body, separators=(",", ":")).encode()
        clean_headers.setdefault("Content-Type", "application/json")
    elif isinstance(body, str):
        payload = body.encode()
    else:
        raise ValueError("Unsupported HTTP body type")
    if payload is not None and len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("Deluge HTTP body too large")
    request = Request(requested, data=payload, method=method, headers=clean_headers)
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        if not 200 <= response.status < 300:
            raise ValueError("Deluge HTTP request returned a non-success status")
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError("Deluge HTTP response exceeds size limit")
    return {"status": "delivered", "bytes": len(data)}
