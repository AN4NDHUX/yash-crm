"""Contract checks for a running Yash CRM instance.

Usage:  YASH_CRM_URL=http://127.0.0.1:8000 python scripts/check_contracts.py

The write checks create records with a unique name and archive them again, so
they are safe to run against a demo database.
"""
from __future__ import annotations

import json
import os
import time
import http.cookiejar
from datetime import date, timedelta
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE = os.getenv("YASH_CRM_URL", "http://127.0.0.1:8000")
USERNAME = os.getenv("YASH_CRM_USERNAME", "")
PASSWORD = os.getenv("YASH_CRM_PASSWORD", "")
OTP = os.getenv("YASH_CRM_OTP", "")
COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = build_opener(HTTPCookieProcessor(COOKIE_JAR))


def request_headers() -> dict[str, str]:
    return {"Accept": "application/json", "Content-Type": "application/json"}


def authenticate() -> None:
    if not USERNAME and not PASSWORD:
        return
    request = Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"identifier": USERNAME, "password": PASSWORD}).encode(),
        method="POST",
        headers=request_headers(),
    )
    with OPENER.open(request) as response:
        body = json.loads(response.read() or b"{}")
        if response.status == 200:
            return
        if response.status != 202 or not body.get("otp_required"):
            raise RuntimeError(f"Yash CRM login failed with HTTP {response.status}")
        if not OTP:
            destination = body.get("destination") or "the registered contact"
            raise RuntimeError(
                "Yash CRM requires a one-time login code. "
                f"Set YASH_CRM_OTP to the 6-digit code sent to {destination}, then run the check again."
            )
        verify = Request(
            f"{BASE}/api/auth/login/verify-otp",
            data=json.dumps({"challenge_id": body.get("challenge_id"), "otp": OTP}).encode(),
            method="POST",
            headers=request_headers(),
        )
        with OPENER.open(verify) as verified:
            if verified.status != 200:
                raise RuntimeError(f"Yash CRM OTP verification failed with HTTP {verified.status}")


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(f"{BASE}{path}", data=data, method=method, headers=request_headers())
    with OPENER.open(request) as response:
        return json.loads(response.read())


def get(path: str) -> dict:
    return call("GET", path)


def status_of(method: str, path: str, body: dict | None = None) -> int:
    try:
        call(method, path, body)
        return 200
    except HTTPError as error:
        return error.code


def read_checks() -> None:
    assert get("/health")["status"] == "ok"
    assert get("/ready")["database"] == "ready"
    assert len(get("/manus-routes.json")["routes"]) >= 10
    dashboard = get("/api/dashboard")
    assert {"total_leads", "open_deals", "pipeline_value", "activities_due", "payments_received", "team_target"} <= set(dashboard["metrics"])
    assert "sales_performance" in dashboard and "attention" in dashboard
    for resource in ("leads", "contacts", "accounts", "deals", "activities"):
        assert get(f"/api/{resource}?limit=1")["total"] >= 1, resource
    assert get("/api/settings/general")["org_name"]
    assert get("/api/settings/profile")["name"]
    ai_status = get("/api/ai/status")
    assert {"configured", "available", "provider", "base_url", "model", "detail", "approval_required", "data_location"} <= set(ai_status), ai_status
    assert ai_status["approval_required"] is True and "api_key" not in ai_status, ai_status
    catalog = get("/api/platform/catalog")
    for resource in ("price_books", "vendors", "quotes", "sales_orders", "purchase_orders", "invoices", "payments", "site_visits", "sales_targets", "campaigns", "cases", "solutions", "documents", "forecasts", "reports", "dashboards", "roles", "profiles", "permissions", "workflow_rules", "integration_settings"):
        assert resource in catalog["resources"], resource
    assert get("/api/activities?activity_type=Task&limit=100")["items"]
    assert get("/api/audit?limit=1")["total"] >= 0

    # Installable-app files must be served as themselves, not swallowed by the SPA fallback.
    manifest = get("/manifest.webmanifest")
    assert manifest["display"] == "standalone" and len(manifest["icons"]) >= 2, manifest
    with OPENER.open(Request(f"{BASE}/sw.js", headers=request_headers())) as response:
        assert response.status == 200 and "javascript" in response.headers.get("Content-Type", "")
        assert b"addEventListener" in response.read(), "sw.js is not the service worker"
    with OPENER.open(Request(f"{BASE}/static/icons/icon-512.png", headers=request_headers())) as response:
        assert response.headers.get("Content-Type") == "image/png"

    with OPENER.open(Request(f"{BASE}/api/dashboard", headers=request_headers())) as response:
        assert response.headers.get("Cache-Control") == "no-store"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


def write_checks() -> None:
    tag = f"Contract check {int(time.time())}"

    # A form submits null for every blank field; model defaults must still apply.
    deal = call("POST", "/api/deals", {"name": tag, "stage": "Proposal", "probability": None, "status": None, "amount": None})
    assert deal["probability"] == 60 and deal["status"] == "Open" and deal["amount"] == 0, deal
    assert any(item["id"] == deal["id"] for item in get(f"/api/deals?status=Proposal&search={quote(tag)}")["items"]), "stage filter"

    # Closing a deal keeps status and probability coherent.
    won = call("PATCH", f"/api/deals/{deal['id']}", {"stage": "Closed Won"})
    assert won["status"] == "Won" and won["probability"] == 100, won

    # Global search finds live records and forgets archived ones.
    assert any(hit["id"] == deal["id"] for hit in get(f"/api/search?q={quote(tag)}")["results"])
    call("DELETE", f"/api/deals/{deal['id']}")
    assert not any(hit["id"] == deal["id"] for hit in get(f"/api/search?q={quote(tag)}")["results"])
    assert status_of("GET", f"/api/deals/{deal['id']}") == 404

    # Notes carry `content`.
    note = call("POST", "/api/notes", {"title": tag, "content": "Body text", "related_type": "deals", "related_id": deal["id"]})
    assert note["content"] == "Body text"
    call("DELETE", f"/api/notes/{note['id']}")

    # Validation and conflicts return clean JSON errors, not 500s.
    assert status_of("POST", "/api/leads", {"company": "No name"}) == 422
    assert status_of("POST", "/api/users", {"name": "Duplicate", "email": "maya@yashcrm.app"}) == 409
    assert status_of("PUT", "/api/settings/general", {"org_name": "   "}) == 422

    # Lead conversion must create and link the account, contact and deal.
    lead = call("POST", "/api/leads", {"name": tag, "company": f"{tag} Ltd", "email": f"contract-{int(time.time())}@example.com"})
    converted = call("POST", f"/api/leads/{lead['id']}/convert", {"deal_name": f"{tag} opportunity", "deal_amount": 1250})
    assert converted["lead"]["status"] == "Converted", converted
    assert converted["lead"]["converted_account_id"] == converted["account"]["id"], converted
    assert converted["lead"]["converted_contact_id"] == converted["contact"]["id"], converted
    assert converted["lead"]["converted_deal_id"] == converted["deal"]["id"], converted

    # Lead-to-cash records inherit customer, opportunity and ownership context.
    owner = get("/api/meta")["users"][0]
    quote_record = call("POST", "/api/platform/quotes", {"name": f"{tag} quote", "deal_id": converted["deal"]["id"], "owner_id": owner["id"], "amount": 1250, "valid_until": (date.today() + timedelta(days=5)).isoformat(), "status": "Sent"})
    assert quote_record["quote_number"].startswith("QUO-") and quote_record["deal_id"] == converted["deal"]["id"], quote_record
    order = call("POST", "/api/platform/sales_orders", {"name": f"{tag} order", "quote_id": quote_record["id"], "due_date": (date.today() + timedelta(days=10)).isoformat(), "status": "Confirmed"})
    assert order["order_number"].startswith("SO-") and order["deal_id"] == converted["deal"]["id"], order
    invoice = call("POST", "/api/platform/invoices", {"name": f"{tag} invoice", "sales_order_id": order["id"], "due_date": (date.today() + timedelta(days=15)).isoformat(), "status": "Issued"})
    assert invoice["invoice_number"].startswith("INV-") and invoice["amount"] == 1250, invoice
    payment = call("POST", "/api/platform/payments", {"name": f"PAY-{int(time.time())}", "invoice_id": invoice["id"], "amount": 1000, "payment_date": date.today().isoformat(), "method": "Bank Transfer", "status": "Cleared"})
    refreshed_invoice = get(f"/api/platform/invoices/{invoice['id']}")
    assert refreshed_invoice["status"] == "Partially Paid" and refreshed_invoice["paid_amount"] == 1000, refreshed_invoice
    visit = call("POST", "/api/platform/site_visits", {"name": f"{tag} visit", "lead_id": lead["id"], "visit_date": date.today().isoformat(), "status": "Completed", "outcome": "Requirements confirmed"})
    target = call("POST", "/api/platform/sales_targets", {"name": f"{tag} target", "owner_id": owner["id"], "period_start": date.today().replace(day=1).isoformat(), "period_end": (date.today() + timedelta(days=31)).isoformat(), "target_amount": 2000000, "incentive_rate": 2, "threshold_percent": 0, "status": "Active"})
    journey = get(f"/api/journey/leads/{lead['id']}")
    assert [stage["key"] for stage in journey["stages"]] == ["lead", "visit", "quotation", "invoice", "payment"], journey
    assert journey["visits"] and journey["quotes"] and journey["invoices"] and journey["payments"], journey
    performance = get("/api/analytics/sales-performance")
    owner_performance = next(item for item in performance["people"] if item["owner_id"] == owner["id"])
    assert owner_performance["target"] == 2000000 and owner_performance["achieved"] >= 1000, owner_performance

    vendor = call("POST", "/api/platform/vendors", {"name": f"{tag} vendor", "status": "Active"})
    purchase_order = call("POST", "/api/platform/purchase_orders", {"name": f"{tag} purchase", "vendor_id": vendor["id"], "amount": 500, "due_date": (date.today() + timedelta(days=20)).isoformat(), "status": "Issued"})
    assert purchase_order["po_number"].startswith("PO-") and purchase_order["related_id"] == vendor["id"], purchase_order

    for resource, item in (("payments", payment), ("invoices", invoice), ("sales_orders", order), ("quotes", quote_record), ("site_visits", visit), ("sales_targets", target), ("purchase_orders", purchase_order), ("vendors", vendor)):
        call("DELETE", f"/api/platform/{resource}/{item['id']}")
    for resource, item in (("leads", converted["lead"]), ("deals", converted["deal"]), ("contacts", converted["contact"]), ("accounts", converted["account"])):
        call("DELETE", f"/api/{resource}/{item['id']}")

    # The initial administrator's profile email remains editable after cloud setup.
    profile = get("/api/settings/profile")
    temporary_email = f"contract-profile-{int(time.time())}@example.com"
    try:
        updated = call("PUT", "/api/settings/profile", {"name": profile["name"], "email": temporary_email})
        assert updated["email"] == temporary_email, updated
    finally:
        call("PUT", "/api/settings/profile", {"name": profile["name"], "email": profile["email"]})

    # Expanded modules are persisted, searchable, editable, related, audited,
    # archived and recoverable rather than being navigation-only placeholders.
    workflow = call("POST", "/api/platform/workflow_rules", {"name": f"{tag} workflow", "module": "cases", "event": "create", "criteria_field": "status", "criteria_value": "New", "action_type": "create_task", "action_value": f"Follow up {tag}", "status": "Active"})
    linked_account = get("/api/accounts?limit=1")["items"][0]
    case = call("POST", "/api/platform/cases", {"name": tag, "case_number": f"CASE-{int(time.time())}", "account_id": linked_account["id"], "priority": "High", "channel": "Web", "status": "New", "description": "Contract test"})
    assert case["name"] == tag and case["status"] == "New", case
    listed = get(f"/api/platform/cases?search={quote(tag)}")
    assert any(item["id"] == case["id"] for item in listed["items"]), listed
    updated_case = call("PATCH", f"/api/platform/cases/{case['id']}", {"status": "In Progress"})
    assert updated_case["status"] == "In Progress", updated_case
    related = get(f"/api/platform/cases/{case['id']}/related")
    assert set(related) == {"accounts", "contacts", "deals", "activities", "platform_records"}, related
    assert related["accounts"][0]["id"] == linked_account["id"], related
    assert any(item["subject"] == f"Follow up {tag}" for item in related["activities"]), related
    call("DELETE", f"/api/platform/cases/{case['id']}")
    recycle = get("/api/administration/recycle-bin")
    assert any(item["resource"] == "cases" and item["id"] == case["id"] for item in recycle["items"]), recycle
    restored = call("POST", "/api/administration/restore", {"resource": "cases", "record_id": case["id"]})
    assert restored["ok"] is True, restored
    call("DELETE", f"/api/platform/cases/{case['id']}")
    audit = get("/api/audit?resource=cases&limit=100")
    assert {item["action"] for item in audit["items"]} >= {"create", "update", "archive", "restore"}, audit
    duplicates = get("/api/administration/duplicates?resource=cases")
    assert duplicates["resource"] == "cases", duplicates
    call("DELETE", f"/api/platform/workflow_rules/{workflow['id']}")


def main() -> None:
    authenticate()
    read_checks()
    write_checks()
    print("Yash CRM contract checks passed")


if __name__ == "__main__":
    main()
