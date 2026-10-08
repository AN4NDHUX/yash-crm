from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def wait_for_server(base: str, timeout: float = 20.0) -> None:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("browser test server did not start")


def test_browser_signup_login_and_module_navigation():
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/browser.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_NAME": "Administrator",
            "SEED_DEMO_DATA": "false",
            "PYTHONPATH": str(ROOT),
        })
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_server(base)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})

                page.goto(base + "/signup")
                page.fill("#name", "Browser User")
                page.fill("#organization-name", "Browser Test Organization")
                page.fill("#username", "browser.user")
                page.fill("#signup-email", "browser.user@example.com")
                page.fill("#password", "browser-password-123")
                page.fill("#confirm-password", "browser-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=10000)
                assert "CONVOSIS CRM" in page.title()
                page.goto(base + "/settings/organization")
                try:
                    page.locator("[data-org-profile] input[name=name]").wait_for(timeout=12000)
                except Exception:
                    raise AssertionError("Organization UI failed to render: " + page.locator("#app-content").inner_text()[:2000] + " | " + page.url)
                page.locator("[data-org-profile] input[name=name]").fill("Browser Renamed Workspace")
                page.locator("[data-org-profile] button[type=submit]").click()
                page.wait_for_function("""async () => {
                  const response = await fetch('/api/organization');
                  return response.ok && (await response.json()).name === 'Browser Renamed Workspace';
                }""")
                page.locator("[data-org-invite] input[name=email]").fill("browser.invited@example.com")
                page.locator("[data-org-invite] button[type=submit]").click()
                page.wait_for_function("""async () => {
                  const response = await fetch('/api/organization/invitations');
                  return response.ok && (await response.json()).items.some(
                    row => row.email === 'browser.invited@example.com' && row.status === 'Pending'
                  );
                }""")

                page.goto(base + "/setup/workflow_rules")
                page.locator("[data-wf-create]").click()
                page.locator("[data-wf-name]").fill("Browser Lead Workflow")
                page.locator("[data-wf-module]").select_option("leads")
                page.locator("[data-wf-next]").click()
                page.locator("[data-wf-event]").select_option("create_or_edit")
                page.locator("[data-wf-next]").click()
                page.locator('input[name="wf-criteria-mode"][value="all"]').check()
                page.locator("[data-wf-next]").click()
                page.locator("[data-wf-action-type='0']").select_option("audit")
                page.locator("[data-wf-next]").click()
                page.wait_for_function("""async () => {
                  const response = await fetch('/api/platform/workflow_rules?limit=100');
                  return response.ok && (await response.json()).items.some(
                    row => row.name === 'Browser Lead Workflow' && row.event === 'create_or_edit'
                  );
                }""")
                assert page.locator("[data-wf-edit]").count() >= 1

                for href in ("/leads", "/deals", "/quotes", "/reports", "/setup"):
                    page.click(f'a[href="{href}"]')
                    page.wait_for_url(f"**{href}**", timeout=10000)
                    assert page.url.startswith(base + href)

                logout = page.evaluate("""async () => {
                    const response = await fetch('/api/auth/logout', {
                        method: 'POST', credentials: 'same-origin'
                    });
                    return {status: response.status, body: await response.text()};
                }""")
                assert logout["status"] == 200, f"Logout failed: {logout}"
                page.goto(base + "/login")
                page.fill("#identifier", "browser.user")
                page.fill("#password", "browser-password-123")
                with page.expect_response(
                    lambda response: "/api/auth/login" in response.url and response.request.method == "POST",
                    timeout=15000,
                ) as login_response:
                    page.click("#submit-button")
                response = login_response.value
                assert response.status == 200, (
                    f"Browser login returned {response.status}: {response.text()[:1000]}"
                )
                page.wait_for_url("**/dashboard", timeout=15000)

                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
