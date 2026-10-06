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
                page.fill("#username", "browser.user")
                page.fill("#signup-email", "browser.user@example.com")
                page.fill("#password", "browser-password-123")
                page.fill("#confirm-password", "browser-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=10000)
                assert "Yash CRM" in page.title()

                for href in ("/leads", "/deals", "/quotes", "/reports", "/setup"):
                    page.click(f'a[href="{href}"]')
                    page.wait_for_url(f"**{href}**", timeout=10000)
                    assert page.url.startswith(base + href)

                page.evaluate("""async () => {
                    await fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'});
                }""")
                page.goto(base + "/login")
                page.fill("#identifier", "browser.user")
                page.fill("#password", "browser-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=10000)

                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
