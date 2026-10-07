from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class BillingError(RuntimeError):
    pass


def configured_provider() -> str:
    provider = os.getenv("YASHCRM_BILLING_PROVIDER", "").strip().lower()
    if provider in {"stripe", "razorpay"}:
        return provider
    return ""


def _post_form(url: str, fields: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = Request(
        url,
        data=urlencode({key: value for key, value in fields.items() if value is not None}).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise BillingError(f"Billing provider rejected checkout creation: {detail}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise BillingError("Billing provider is temporarily unavailable.") from exc


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise BillingError(f"Billing provider rejected checkout creation: {detail}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise BillingError("Billing provider is temporarily unavailable.") from exc


def create_hosted_checkout(
    *,
    request_id: int,
    plan_name: str,
    amount_major: float,
    currency: str,
    seats: int,
    customer_email: str,
    public_url: str,
) -> dict[str, Any]:
    provider = configured_provider()
    if not provider:
        raise BillingError("Billing provider is not configured.")

    amount_minor = max(1, int(round(float(amount_major) * 100)))
    seats = max(1, int(seats))
    public_url = public_url.rstrip("/")

    if provider == "stripe":
        secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
        if not secret:
            raise BillingError("STRIPE_SECRET_KEY is not configured.")
        fields = {
            "mode": "subscription",
            "success_url": f"{public_url}/subscriptions?checkout=success",
            "cancel_url": f"{public_url}/subscriptions?checkout=cancelled",
            "client_reference_id": str(request_id),
            "customer_email": customer_email,
            "metadata[request_id]": str(request_id),
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][product_data][name]": f"Yash CRM {plan_name}",
            "line_items[0][price_data][unit_amount]": str(amount_minor),
            "line_items[0][price_data][recurring][interval]": "month",
            "line_items[0][quantity]": str(seats),
        }
        data = _post_form(
            "https://api.stripe.com/v1/checkout/sessions",
            fields,
            {"Authorization": f"Bearer {secret}"},
        )
        return {
            "provider": "stripe",
            "provider_reference": data.get("id"),
            "checkout_url": data.get("url"),
            "raw_status": data.get("status"),
        }

    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        raise BillingError("Razorpay credentials are not configured.")
    auth = base64.b64encode(f"{key_id}:{key_secret}".encode("utf-8")).decode("ascii")
    reference = f"yash-upgrade-{request_id}"
    payload = {
        "amount": amount_minor * seats,
        "currency": currency.upper(),
        "accept_partial": False,
        "reference_id": reference,
        "description": f"Yash CRM {plan_name} - {seats} user(s)",
        "customer": {"email": customer_email},
        "notify": {"email": True, "sms": False},
        "reminder_enable": True,
        "callback_url": f"{public_url}/subscriptions?checkout=success",
        "callback_method": "get",
        "notes": {
            "yashcrm_request_id": str(request_id),
            "plan_name": plan_name,
            "seats": str(seats),
        },
    }
    data = _post_json(
        "https://api.razorpay.com/v1/payment_links",
        payload,
        {"Authorization": f"Basic {auth}"},
    )
    return {
        "provider": "razorpay",
        "provider_reference": data.get("id") or reference,
        "checkout_url": data.get("short_url"),
        "raw_status": data.get("status"),
    }


def verify_webhook(provider: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
    provider = provider.strip().lower()
    if provider == "razorpay":
        secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
        signature = headers.get("x-razorpay-signature", "")
        if not secret or not signature:
            raise BillingError("Razorpay webhook signature is unavailable.")
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise BillingError("Invalid Razorpay webhook signature.")
        event = json.loads(body.decode("utf-8"))
        link = (((event.get("payload") or {}).get("payment_link") or {}).get("entity") or {})
        reference = str(link.get("reference_id") or "")
        request_id = int(reference.rsplit("-", 1)[-1]) if reference.startswith("yash-upgrade-") else None
        paid = str(event.get("event") or "") == "payment_link.paid"
        return {
            "verified": True,
            "paid": paid,
            "request_id": request_id,
            "provider_reference": link.get("id") or reference,
            "event_type": event.get("event"),
            "raw": event,
        }

    if provider == "stripe":
        secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
        signature_header = headers.get("stripe-signature", "")
        if not secret or not signature_header:
            raise BillingError("Stripe webhook signature is unavailable.")
        parts: dict[str, list[str]] = {}
        for part in signature_header.split(","):
            key, _, value = part.partition("=")
            parts.setdefault(key.strip(), []).append(value.strip())
        try:
            timestamp = int((parts.get("t") or ["0"])[0])
        except ValueError as exc:
            raise BillingError("Invalid Stripe webhook timestamp.") from exc
        if abs(int(time.time()) - timestamp) > 300:
            raise BillingError("Stripe webhook timestamp is outside the allowed tolerance.")
        signed_payload = f"{timestamp}.".encode("utf-8") + body
        expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in parts.get("v1", [])):
            raise BillingError("Invalid Stripe webhook signature.")
        event = json.loads(body.decode("utf-8"))
        obj = ((event.get("data") or {}).get("object") or {})
        metadata = obj.get("metadata") or {}
        raw_request_id = metadata.get("request_id") or obj.get("client_reference_id")
        request_id = int(raw_request_id) if str(raw_request_id or "").isdigit() else None
        event_type = str(event.get("type") or "")
        paid = (
            event_type == "checkout.session.async_payment_succeeded"
            or (event_type == "checkout.session.completed" and str(obj.get("payment_status") or "").lower() == "paid")
            or event_type == "invoice.paid"
        )
        return {
            "verified": True,
            "paid": paid,
            "request_id": request_id,
            "provider_reference": obj.get("subscription") or obj.get("id"),
            "event_type": event_type,
            "raw": event,
        }

    raise BillingError("Unsupported billing provider.")
