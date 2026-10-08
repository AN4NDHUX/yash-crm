from __future__ import annotations

import json
import os
import sys
import uuid
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = os.getenv("PRODUCTION_BASE_URL", "https://yashcrm-production.up.railway.app").rstrip("/")
EXPECTED_APP_REVISION = os.getenv("EXPECTED_APP_REVISION", "").strip()
EXPECTED_MIGRATION_REVISION = os.getenv("EXPECTED_MIGRATION_REVISION", "").strip()
ADMIN_USERNAME = os.getenv("PRODUCTION_ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD = os.getenv("PRODUCTION_ADMIN_PASSWORD", "")
USER_A_IDENTIFIER = os.getenv("PRODUCTION_SMOKE_USER_A_IDENTIFIER", "").strip()
USER_A_PASSWORD = os.getenv("PRODUCTION_SMOKE_USER_A_PASSWORD", "")
USER_B_IDENTIFIER = os.getenv("PRODUCTION_SMOKE_USER_B_IDENTIFIER", "").strip()
USER_B_PASSWORD = os.getenv("PRODUCTION_SMOKE_USER_B_PASSWORD", "")


def client():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def call(opener, method: str, path: str, payload=None, headers=None, expected=(200,)):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        # Production cookie-authenticated writes require a same-origin browser source.
        # Preserve CSRF enforcement instead of weakening application middleware.
        parsed_base = urlsplit(BASE_URL)
        request_headers.setdefault("Origin", f"{parsed_base.scheme}://{parsed_base.netloc}")
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    req = Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with opener.open(req, timeout=30) as response:
            raw = response.read()
            status = response.status
            text = raw.decode("utf-8", errors="replace")
    except HTTPError as error:
        status = error.code
        text = error.read().decode("utf-8", errors="replace")
    except URLError as error:
        raise AssertionError(f"{method} {path} could not reach production: {error}") from error
    if status not in expected:
        raise AssertionError(f"{method} {path} returned {status}, expected {expected}: {text[:800]}")
    try:
        return status, json.loads(text) if text else {}
    except json.JSONDecodeError:
        return status, text


def verify_public_readiness():
    opener = client()
    _, health = call(opener, "GET", "/health")
    assert health.get("status") == "ok", health
    _, ready = call(opener, "GET", "/ready")
    assert ready.get("status") == "ok", ready
    assert ready.get("database") == "ready", ready

    live_revision = str(ready.get("app_revision") or "")
    live_migration = str(ready.get("migration_revision") or "")
    assert EXPECTED_APP_REVISION, "EXPECTED_APP_REVISION is required for release verification"
    assert EXPECTED_MIGRATION_REVISION, "EXPECTED_MIGRATION_REVISION is required for release verification"
    assert live_revision and live_revision != "unknown" and len(live_revision) >= 7, (
        f"Production app revision missing or invalid: {live_revision!r}"
    )
    assert live_migration and live_migration != "unknown", (
        f"Production migration revision missing: {live_migration!r}"
    )
    assert live_revision.startswith(EXPECTED_APP_REVISION) or (
        len(EXPECTED_APP_REVISION) >= 7 and EXPECTED_APP_REVISION.startswith(live_revision)
    ), f"Production revision mismatch: live={live_revision!r} expected={EXPECTED_APP_REVISION!r}"
    assert live_migration == EXPECTED_MIGRATION_REVISION, (
        f"Production migration mismatch: live={live_migration!r} expected={EXPECTED_MIGRATION_REVISION!r}"
    )
    return {"health": health, "ready": ready}


def login(identifier: str, password: str):
    opener = client()
    _, payload = call(opener, "POST", "/api/auth/login", {
        "identifier": identifier,
        "password": password,
    })
    assert payload.get("ok") is True, payload
    return opener, payload


def verify_admin_auth():
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise AssertionError("PRODUCTION_ADMIN_USERNAME / PRODUCTION_ADMIN_PASSWORD secrets are required")
    opener, payload = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    status, _ = call(opener, "GET", "/owner", expected=(200,))
    assert status == 200
    call(opener, "POST", "/api/auth/logout", {}, expected=(200,))
    call(opener, "GET", "/api/auth/session", expected=(401,))
    return {"admin": payload.get("user", {}).get("username"), "owner_page": status}


def verify_tenant_isolation():
    missing = [
        name for name, value in {
            "PRODUCTION_SMOKE_USER_A_IDENTIFIER": USER_A_IDENTIFIER,
            "PRODUCTION_SMOKE_USER_A_PASSWORD": USER_A_PASSWORD,
            "PRODUCTION_SMOKE_USER_B_IDENTIFIER": USER_B_IDENTIFIER,
            "PRODUCTION_SMOKE_USER_B_PASSWORD": USER_B_PASSWORD,
        }.items() if not value
    ]
    if missing:
        raise AssertionError("Missing tenant-smoke secrets: " + ", ".join(missing))

    tag = "tier0-smoke-" + uuid.uuid4().hex[:12]
    a, _ = login(USER_A_IDENTIFIER, USER_A_PASSWORD)
    _, lead = call(a, "POST", "/api/leads", {"name": tag, "company": "Tier 0 production smoke"})
    lead_id = int(lead["id"])

    b, _ = login(USER_B_IDENTIFIER, USER_B_PASSWORD)
    call(b, "GET", f"/api/leads/{lead_id}", expected=(404,))
    call(b, "GET", "/api/users", expected=(403,))

    # Clean up the disposable record from Tenant A after proving isolation.
    call(a, "POST", "/api/leads/bulk-archive", {"related_id": [lead_id]}, expected=(200,))
    return {"lead_id": lead_id, "cross_tenant_status": 404, "admin_denial": 403}


def verify_billing_rejects_unsigned_events():
    opener = client()
    stripe_status, _ = call(
        opener, "POST", "/api/billing/webhook/stripe", {},
        headers={"Stripe-Signature": "t=0,v1=invalid"},
        expected=(400,),
    )
    razorpay_status, _ = call(
        opener, "POST", "/api/billing/webhook/razorpay", {},
        headers={"X-Razorpay-Signature": "invalid"},
        expected=(400,),
    )
    return {"stripe": stripe_status, "razorpay": razorpay_status}


def main() -> int:
    results = {
        "public_readiness": verify_public_readiness(),
        "admin_auth": verify_admin_auth(),
        "tenant_isolation": verify_tenant_isolation(),
        "billing_signature_rejection": verify_billing_rejects_unsigned_events(),
    }
    print(json.dumps({"ok": True, "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise
