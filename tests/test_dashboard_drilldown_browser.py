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


def test_dashboard_cards_open_live_reports_in_browser():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{tmp}/browser.db",
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
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/health", timeout=1):
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise AssertionError("CRM browser-test server failed to start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(base + "/signup")
                page.fill("#name", "Dashboard Browser User")
                page.fill("#organization-name", "Dashboard Browser Organization")
                page.fill("#username", "dashboard.browser")
                page.fill("#signup-email", "dashboard.browser@example.com")
                page.fill("#password", "dashboard-password-123")
                page.fill("#confirm-password", "dashboard-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=15000)
                # URL navigation precedes async SPA rendering; report actual
                # page and API state if the dashboard fails to become ready.
                first_metric = page.locator('.stats-grid [data-go="/dashboard/report/total-leads"]')
                try:
                    first_metric.wait_for(state="visible", timeout=15000)
                except Exception as error:
                    dashboard_api = page.evaluate("""async () => {
                        const response = await fetch('/api/dashboard');
                        return {status: response.status, body: (await response.text()).slice(0, 1500)};
                    }""")
                    content = (page.locator("#app-content").inner_text(timeout=5000)
                               if page.locator("#app-content").count()
                               else page.locator("body").inner_text())
                    raise AssertionError(
                        f"Dashboard KPI not rendered: {error}; page={page.url}; "
                        f"content={content[:1600]!r}; api={dashboard_api!r}"
                    ) from error
                for key in ("total-leads", "open-deals", "pipeline-value", "activities-due"):
                    page.locator(f'.stats-grid [data-go="/dashboard/report/{key}"]').click()
                    page.wait_for_url(f"**/dashboard/report/{key}", timeout=15000)
                    page.locator(f'[data-dashboard-report="{key}"]').wait_for(timeout=15000)
                    page.locator('[data-go="/dashboard"]').click()
                    page.wait_for_url("**/dashboard", timeout=15000)
                page.locator('[data-go="/dashboard/report/ai-action-queue"]').click()
                page.wait_for_url("**/dashboard/report/ai-action-queue", timeout=15000)
                page.locator('[data-dashboard-report="ai-action-queue"]').wait_for(timeout=15000)
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
