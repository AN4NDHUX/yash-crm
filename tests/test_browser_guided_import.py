"""Chromium regression for Zoho-style imports across all four core modules."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_browser_guided_import_all_four_modules():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV":"development", "DATABASE_URL":f"sqlite:///{tmp}/guided-browser.db",
            "ENABLE_AUTH":"true", "APP_USERNAME":"admin",
            "APP_PASSWORD":"supersecretpass123", "ADMIN_EMAIL":"admin@example.com",
            "SEED_DEMO_DATA":"false", "PYTHONPATH":str(ROOT),
        })
        server = subprocess.Popen(
            [sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(port)],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,
        )
        try:
            import urllib.request
            for _ in range(120):
                try:
                    with urllib.request.urlopen(base+"/health", timeout=1):
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise AssertionError("CRM browser server failed to start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width":1440,"height":900})
                page.goto(base+"/signup")
                page.fill("#name","Guided Import Browser User")
                page.fill("#organization-name","Guided Import Browser Workspace")
                page.fill("#username","guided.import.browser")
                page.fill("#signup-email","guided.browser@example.com")
                page.fill("#password","guided-import-password-123")
                page.fill("#confirm-password","guided-import-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard",timeout=15000)
                expected_modules = ["leads", "deals", "accounts", "contacts"]
                for resource in expected_modules:
                    page.goto(base + "/setup/import")
                    module_select = page.locator("#setup-import-module")
                    module_select.wait_for(timeout=15000)
                    assert module_select.locator("option").evaluate_all(
                        "(options) => options.map(option => option.value)"
                    ) == expected_modules
                    module_select.select_option(resource)
                    page.locator("[data-setup-import-selector] button[type=submit]").click()
                    page.wait_for_url("**/import/" + resource, timeout=15000)
                    page.locator("[data-import-drop]").wait_for(state="visible",timeout=10000)
                    page.locator("[data-import-files]").wait_for(state="attached",timeout=10000)
                for resource in ("leads","deals","accounts","contacts"):
                    file_body = (
                        b"First Name,Last Name,Phone Number\nAva,Smith,+911234567890\n"
                        if resource=="contacts"
                        else f"Full Name,Phone Number\nBrowser {resource},+91123456789{len(resource)}\n".encode()
                    )
                    page.goto(base+"/"+resource)
                    entry = page.locator(f'[data-start-import="{resource}"]')
                    entry.wait_for(timeout=15000)
                    entry.click()
                    page.wait_for_url("**/import/"+resource)
                    page.locator("[data-import-files]").set_input_files({
                        "name":"import.csv","mimeType":"text/csv","buffer":file_body
                    })
                    with page.expect_response(lambda res: res.url.endswith("/api/import-wizard/"+resource+"/preview"), timeout=20000) as preview_event:
                        page.locator("[data-import-next]").click()
                    preview_response = preview_event.value
                    assert preview_response.status == 200, (
                        resource, preview_response.status, preview_response.text()[:1200],
                        page.locator("#app-content").inner_text()[:1200]
                    )
                    try:
                        page.locator("input[name=import-operation]").first.wait_for(timeout=8000)
                    except Exception as error:
                        raise AssertionError(
                            "Import wizard did not advance: " + resource
                            + " | preview=" + preview_response.text()[:700]
                            + " | UI=" + page.locator("#app-content").inner_text()[:1600]
                            + " | alerts=" + page.locator("body").inner_text()[-500:]
                        ) from error
                    page.locator("[data-import-next]").click()
                    page.locator(".import-target-card").wait_for()
                    page.locator("[data-import-next]").click()
                    phone=page.locator('select[data-import-map="Phone Number"]')
                    phone.wait_for()
                    assert phone.input_value()=="phone",resource
                    phone.select_option("")
                    page.locator("[data-import-next]").click()
                    assert page.locator(".import-mapping-required").is_visible()
                    phone.select_option("phone")
                    page.locator("[data-import-next]").click()
                    page.locator("[data-import-automation]").wait_for()
                    page.locator("[data-import-next]").click()
                    page.wait_for_url("**/setup/import_history",timeout=20000)
                    page.get_by_text("Import History",exact=True).first.wait_for()
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
