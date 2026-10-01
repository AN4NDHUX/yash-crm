"""Contract checks for a running Yash CRM instance.

Usage:  YASH_CRM_URL=http://127.0.0.1:8000 python scripts/check_contracts.py

The write checks create records with a unique name and archive them again, so
they are safe to run against a demo database.
"""
from __future__ import annotations

import json
import os
import time
import base64
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = os.getenv("YASH_CRM_URL", "http://127.0.0.1:8000")
USERNAME = os.getenv("YASH_CRM_USERNAME", "")
PASSWORD = os.getenv("YASH_CRM_PASSWORD", "")


def request_headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if USERNAME or PASSWORD:
        token = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    return headers


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(f"{BASE}{path}", data=data, method=method, headers=request_headers())
    with urlopen(request) as response:
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
    assert set(dashboard["metrics"]) == {"total_leads", "open_deals", "pipeline_value", "activities_due"}
    for resource in ("leads", "contacts", "accounts", "deals", "activities"):
        assert get(f"/api/{resource}?limit=1")["total"] >= 1, resource
    assert get("/api/settings/general")["org_name"]
    assert get("/api/settings/profile")["name"]
    catalog = get("/api/platform/catalog")
    for resource in ("price_books", "vendors", "quotes", "sales_orders", "purchase_orders", "invoices", "campaigns", "cases", "solutions", "documents", "forecasts", "reports", "dashboards", "roles", "profiles", "permissions", "workflow_rules", "integration_settings"):
        assert resource in catalog["resources"], resource
    assert get("/api/activities?activity_type=Task&limit=100")["items"]
    assert get("/api/audit?limit=1")["total"] >= 0

    # Installable-app files must be served as themselves, not swallowed by the SPA fallback.
    manifest = get("/manifest.webmanifest")
    assert manifest["display"] == "standalone" and len(manifest["icons"]) >= 2, manifest
    with urlopen(Request(f"{BASE}/sw.js", headers=request_headers())) as response:
        assert response.status == 200 and "javascript" in response.headers.get("Content-Type", "")
        assert b"addEventListener" in response.read(), "sw.js is not the service worker"
    with urlopen(Request(f"{BASE}/static/icons/icon-512.png", headers=request_headers())) as response:
        assert response.headers.get("Content-Type") == "image/png"

    with urlopen(Request(f"{BASE}/api/dashboard", headers=request_headers())) as response:
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
    read_checks()
    write_checks()
    print("Yash CRM contract checks passed")


if __name__ == "__main__":
    main()
