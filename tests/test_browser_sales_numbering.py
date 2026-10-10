"""Chromium checks real numbered record Open/Edit/Delete flows."""
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_numbered_products_and_platform_records_can_open_edit_delete():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as temp:
        db_path = f"{temp}/numbering-browser.db"
        env = {**os.environ,
            "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db_path}",
            "ENABLE_AUTH": "true", "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123", "ADMIN_EMAIL": "admin@example.com",
            "SEED_DEMO_DATA": "false", "PYTHONPATH": str(ROOT)}
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
             "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        try:
            import urllib.request
            for _ in range(120):
                try:
                    with urllib.request.urlopen(base + "/health", timeout=1):
                        break
                except Exception:
                    time.sleep(.2)
            else:
                raise AssertionError("Browser test server could not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 980})
                browser_errors = []
                page.on("pageerror", lambda e: browser_errors.append(str(e)))
                page.goto(base + "/signup")
                page.fill("#name", "Numbered Sales Browser")
                page.fill("#organization-name", "Sales Numbering Browser Org")
                page.fill("#username", "numbering.browser")
                page.fill("#signup-email", "numbering.browser@example.test")
                page.fill("#password", "strong-password-123")
                page.fill("#confirm-password", "strong-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=15000)
                with sqlite3.connect(db_path) as db:
                    db.execute("UPDATE organization_subscriptions SET plan_id="
                               "(SELECT id FROM plans WHERE code='professional')")
                    db.commit()

                page.goto(base + "/products")
                page.locator('[data-create="products"]').click()
                number = page.locator('#modal-body [name="record_number"]')
                assert number.is_visible() and number.get_attribute("readonly") is not None
                page.locator('#modal-body [name="name"]').fill("Browser Valve")
                page.locator("#modal-submit").click()
                page.locator("#modal-backdrop").wait_for(state="hidden", timeout=15000)
                page.locator('[data-open-record="products"]').first.click()
                page.wait_for_url("**/products/*", timeout=12000)
                page.get_by_text(re.compile(r"^PRD\d{5}$")).first.wait_for(timeout=15000)
                page.locator('[data-edit-record="products"]').first.click()
                assert page.locator('#modal-body [name="record_number"]').get_attribute("readonly") is not None
                page.locator('#modal-body [name="sku"]').fill("SKU-ABC")
                page.locator("#modal-submit").click()
                page.locator("#modal-backdrop").wait_for(state="hidden", timeout=15000)
                assert "SKU-ABC" in page.locator("#app-content").inner_text()
                page.locator('[data-delete-record="products"]').first.click()
                page.locator("#confirm-action").click()
                page.wait_for_url("**/products", timeout=12000)

                for resource, prefix in (("price_books", "PB"), ("vendors", "VND")):
                    page.goto(base + "/" + resource)
                    try:
                        page.locator(f'[data-platform-create="{resource}"]').first.wait_for(timeout=8000)
                    except Exception as error:
                        raise AssertionError("Missing platform Create button for "+resource+
                            "; page="+page.locator("#app-content").inner_text()[:1500]+
                            "; browser errors="+str(browser_errors)) from error
                    page.locator(f'[data-platform-create="{resource}"]').first.click()
                    number = page.locator('#modal-body [name="record_number"]')
                    assert number.get_attribute("readonly") is not None
                    page.locator('#modal-body [name="name"]').fill("Browser " + resource)
                    page.locator("#modal-submit").click()
                    page.locator("#modal-backdrop").wait_for(state="hidden", timeout=15000)
                    page.locator(f'[data-platform-open="{resource}"]').first.click()
                    page.wait_for_url("**/" + resource + "/*", timeout=15000)
                    page.get_by_text(re.compile(r"^"+prefix+r"\d{5}$")).first.wait_for(timeout=15000)
                    page.locator('[data-platform-detail-edit]').first.click()
                    number = page.locator('#modal-body [name="record_number"]')
                    assert number.get_attribute("readonly") is not None
                    page.locator('#modal-body [name="name"]').fill("Updated " + resource)
                    page.locator("#modal-submit").click()
                    page.locator("#modal-backdrop").wait_for(state="hidden", timeout=15000)
                    page.get_by_text("Updated " + resource,exact=True).first.wait_for(timeout=15000)
                    page.locator('[data-platform-detail-delete]').first.click()
                    page.locator("#confirm-action").click()
                    page.wait_for_url("**/" + resource, timeout=15000)
                    assert page.locator(f'[data-platform-open="{resource}"]').count() == 0
                assert not browser_errors, browser_errors
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
