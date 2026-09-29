"""Contract checks for a running Yash CRM instance.

Usage:  YASH_CRM_URL=http://127.0.0.1:3000 python scripts/check_contracts.py

The write checks create records with a unique name and archive them again, so
they are safe to run against a demo database.
"""
from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = os.getenv("YASH_CRM_URL", "http://127.0.0.1:3000")


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(f"{BASE}{path}", data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
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
    assert len(get("/manus-routes.json")["routes"]) >= 10
    dashboard = get("/api/dashboard")
    assert set(dashboard["metrics"]) == {"total_leads", "open_deals", "pipeline_value", "activities_due"}
    for resource in ("leads", "contacts", "accounts", "deals", "activities"):
        assert get(f"/api/{resource}?limit=1")["total"] >= 1, resource
    assert get("/api/settings/general")["org_name"]
    assert get("/api/settings/profile")["name"]

    # Installable-app files must be served as themselves, not swallowed by the SPA fallback.
    manifest = get("/manifest.webmanifest")
    assert manifest["display"] == "standalone" and len(manifest["icons"]) >= 2, manifest
    with urlopen(Request(f"{BASE}/sw.js")) as response:
        assert response.status == 200 and "javascript" in response.headers.get("Content-Type", "")
        assert b"addEventListener" in response.read(), "sw.js is not the service worker"
    with urlopen(Request(f"{BASE}/static/icons/icon-512.png")) as response:
        assert response.headers.get("Content-Type") == "image/png"


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


def main() -> None:
    read_checks()
    write_checks()
    print("Yash CRM contract checks passed")


if __name__ == "__main__":
    main()
