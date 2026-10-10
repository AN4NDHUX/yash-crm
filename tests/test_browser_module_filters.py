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


def test_browser_advanced_filters_all_four_core_modules():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{tmp}/filters-browser.db",
            "ENABLE_AUTH": "true", "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123", "ADMIN_EMAIL": "admin@example.com",
            "SEED_DEMO_DATA": "false", "PYTHONPATH": str(ROOT),
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
                raise AssertionError("Filter browser server failed to start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width":1440,"height":900})
                page.goto(base + "/signup")
                page.fill("#name", "Filter Browser User")
                page.fill("#organization-name", "Filter Browser Organization")
                page.fill("#username", "filter.browser")
                page.fill("#signup-email", "filter.browser@example.com")
                page.fill("#password", "filter-browser-password-123")
                page.fill("#confirm-password", "filter-browser-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=15000)
                for resource,field in (
                    ("leads","name"), ("deals","name"),
                    ("accounts","name"), ("contacts","first_name"),
                ):
                    page.goto(base + "/" + resource)
                    toggle = page.locator("[data-filter-toggle]")
                    toggle.wait_for(timeout=15000)
                    toggle.click()
                    panel = page.locator("[data-filter-sidebar]")
                    panel.wait_for(state="visible",timeout=10000)
                    assert panel.get_by_text("System Defined Filters").count() == 1
                    assert panel.get_by_text("Filter By Fields").count() == 1
                    assert panel.get_by_text("Filter By Related Modules").count() == 1
                    panel.locator("[data-filter-search]").fill(field.replace("_"," "))
                    box = panel.locator(f'[data-filter-check="field:{field}"]')
                    box.check()
                    controls = panel.locator(f'[data-filter-condition="field:{field}"]')
                    controls.locator("[data-filter-value]").fill("not-a-matching-record")
                    panel.locator("[data-filter-apply]").click()
                    page.locator("[data-filter-sidebar]").wait_for(state="visible",timeout=10000)
                    assert page.locator("[data-filter-toggle]").get_attribute("aria-expanded") == "true"
                    assert page.locator("[data-filter-toggle]").inner_text().endswith("(1)")
                    page.locator("[data-filter-reset]").click()
                    page.locator("[data-filter-sidebar]").wait_for(state="visible",timeout=10000)
                    assert "(1)" not in page.locator("[data-filter-toggle]").inner_text()
                    page.locator("[data-filter-close]").click()
                    page.locator("[data-filter-sidebar]").wait_for(state="hidden",timeout=10000)
                page.set_viewport_size({"width":390,"height":844})
                page.goto(base + "/accounts")
                page.locator("[data-filter-toggle]").click()
                page.locator("[data-filter-sidebar]").wait_for(state="visible",timeout=10000)
                assert page.locator(".advanced-filter-layout.filters-visible").count() == 1
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
