"""Chromium check that sales-module status menus match their actual status definitions."""
from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "quotes": ["Draft", "Pending Approval", "Approved", "Sent", "Accepted", "Closed", "Cancelled"],
    "sales_orders": ["Draft", "Confirmed", "In Fulfilment", "Fulfilled", "Cancelled"],
    "purchase_orders": ["Draft", "Issued", "Partially Received", "Received", "Cancelled"],
    "invoices": ["Draft", "Issued", "Partially Paid", "Paid", "Overdue", "Void"],
    "payments": ["Pending", "Received", "Cleared", "Failed", "Refunded"],
}


def test_sales_module_dropdowns_show_module_specific_statuses_and_filter():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as folder:
        db_path = f"{folder}/platform-status.db"
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db_path}",
            "ENABLE_AUTH": "true", "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com", "SEED_DEMO_DATA": "false",
            "PYTHONPATH": str(ROOT),
        })
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        try:
            import urllib.request
            for _ in range(120):
                try:
                    with urllib.request.urlopen(base + "/health", timeout=1):
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise AssertionError("Browser CRM server did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/signup")
                page.fill("#name", "Status Dropdown User")
                page.fill("#organization-name", "Status Dropdown Workspace")
                page.fill("#username", "status.dropdown.user")
                page.fill("#signup-email", "dropdown@example.test")
                page.fill("#password", "dropdown-password-123")
                page.fill("#confirm-password", "dropdown-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=15000)
                # Fixture only: the product enforces inventory permissions by plan.
                with sqlite3.connect(db_path) as connection:
                    connection.execute(
                        "UPDATE organization_subscriptions SET plan_id="
                        "(SELECT id FROM plans WHERE code='professional')"
                    )
                    connection.commit()
                for resource, options in EXPECTED.items():
                    page.goto(base + "/" + resource)
                    select = page.locator(f'[data-platform-status="{resource}"]')
                    select.wait_for(timeout=16000)
                    actual = select.locator("option").evaluate_all(
                        "(options) => options.map(option => option.value)"
                    )
                    assert actual == [""] + options, (resource, actual)
                    # Verify the selected status is sent to the real list API.
                    chosen = options[-1]
                    with page.expect_response(
                        lambda response: (
                            urlsplit(response.url).path == "/api/platform/" + resource
                            and parse_qs(urlsplit(response.url).query).get("status") == [chosen]
                        ),
                        timeout=15000,
                    ) as result:
                        select.select_option(chosen)
                    assert result.value.status == 200, (
                        resource, chosen, result.value.status, result.value.text()[:500]
                    )
                    updated = page.locator(f'[data-platform-status="{resource}"]')
                    updated.wait_for(timeout=12000)
                    assert updated.input_value() == chosen, resource
                    updated.select_option("")
                    assert updated.input_value() == "", resource
                assert not errors, errors
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
