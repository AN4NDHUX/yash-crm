from __future__ import annotations

import json

from app import billing


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_razorpay_payment_link_uses_json_contract(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=25):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = request.data
        return _FakeResponse({
            "id": "plink_test",
            "short_url": "https://rzp.io/i/example",
            "status": "created",
        })

    monkeypatch.setenv("YASHCRM_BILLING_PROVIDER", "razorpay")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "rzp_test_secret")
    monkeypatch.setattr(billing, "urlopen", fake_urlopen)

    result = billing.create_hosted_checkout(
        request_id=42,
        plan_name="Professional",
        amount_major=1400,
        currency="INR",
        seats=3,
        customer_email="billing@example.com",
        public_url="https://crm.example.com",
    )

    payload = json.loads(captured["body"].decode("utf-8"))
    assert captured["url"] == "https://api.razorpay.com/v1/payment_links"
    assert captured["headers"]["content-type"] == "application/json"
    assert payload["amount"] == 420000
    assert payload["currency"] == "INR"
    assert payload["accept_partial"] is False
    assert payload["reference_id"] == "yash-upgrade-42"
    assert payload["customer"]["email"] == "billing@example.com"
    assert payload["notify"]["email"] is True
    assert payload["callback_method"] == "get"
    assert payload["notes"]["yashcrm_request_id"] == "42"
    assert result["provider"] == "razorpay"
    assert result["checkout_url"] == "https://rzp.io/i/example"


def test_stripe_checkout_remains_form_encoded(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=25):
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = request.data.decode("utf-8")
        return _FakeResponse({
            "id": "cs_test",
            "url": "https://checkout.stripe.com/example",
            "status": "open",
        })

    monkeypatch.setenv("YASHCRM_BILLING_PROVIDER", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setattr(billing, "urlopen", fake_urlopen)

    result = billing.create_hosted_checkout(
        request_id=43,
        plan_name="Professional",
        amount_major=1400,
        currency="INR",
        seats=2,
        customer_email="stripe@example.com",
        public_url="https://crm.example.com",
    )

    assert captured["headers"]["content-type"] == "application/x-www-form-urlencoded"
    assert "client_reference_id=43" in captured["body"]
    assert "line_items%5B0%5D%5Bquantity%5D=2" in captured["body"]
    assert result["provider"] == "stripe"
    assert result["checkout_url"] == "https://checkout.stripe.com/example"


def test_stripe_webhook_requires_paid_checkout_status(monkeypatch):
    import hashlib
    import hmac
    import time

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    def signed(payload: dict) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        timestamp = int(time.time())
        signature = hmac.new(
            b"whsec_test",
            f"{timestamp}.".encode("utf-8") + body,
            hashlib.sha256,
        ).hexdigest()
        return body, {"stripe-signature": f"t={timestamp},v1={signature}"}

    unpaid_body, unpaid_headers = signed({
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_unpaid",
            "client_reference_id": "42",
            "payment_status": "unpaid",
            "metadata": {"request_id": "42"},
        }},
    })
    unpaid = billing.verify_webhook("stripe", unpaid_body, unpaid_headers)
    assert unpaid["verified"] is True
    assert unpaid["paid"] is False
    assert unpaid["request_id"] == 42

    paid_body, paid_headers = signed({
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_paid",
            "client_reference_id": "42",
            "payment_status": "paid",
            "metadata": {"request_id": "42"},
        }},
    })
    paid = billing.verify_webhook("stripe", paid_body, paid_headers)
    assert paid["paid"] is True

    async_body, async_headers = signed({
        "type": "checkout.session.async_payment_succeeded",
        "data": {"object": {
            "id": "cs_async",
            "client_reference_id": "42",
            "payment_status": "paid",
            "metadata": {"request_id": "42"},
        }},
    })
    async_paid = billing.verify_webhook("stripe", async_body, async_headers)
    assert async_paid["paid"] is True
