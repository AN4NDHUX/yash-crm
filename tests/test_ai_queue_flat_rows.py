"""Prevent compact boxed record buttons across AI and dashboard action queues."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_both_ai_queues_use_full_width_unboxed_record_rows():
    apex = (ROOT / "static/js/features/ai.js").read_text(encoding="utf-8")
    dashboard = (ROOT / "static/js/features/dashboard-support.js").read_text(encoding="utf-8")
    css = (ROOT / "static/css/foundation.css").read_text(encoding="utf-8")
    apex_queue = apex.split("const blockers = [", 1)[1].split("].join(\"\");", 1)[0]
    assert apex_queue.count('class="ai-queue-row"') == 2
    assert 'class="related-item"' not in apex_queue
    assert 'data-go="/quotes/${Number(item.id)}"' in apex_queue
    assert 'data-go="/leads/${Number(item.id)}"' in apex_queue
    assert 'class="ai-queue-list"' in apex
    assert dashboard.count('class="ai-queue-row"') == 2
    assert 'class="ai-queue-list"' in dashboard
    rows = css.split(".ai-queue-row {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in rows
    assert "border: 0" in rows
    assert "box-shadow: none" in rows
    assert "background: transparent" in rows
    assert ":is(button, a).related-item {" in css
    assert ":is(button, a).related-item:focus-visible" in css


def test_apex_attention_queue_browser_appearance_and_navigation():
    import os
    import socket
    import subprocess
    import sys
    import tempfile
    import time
    import urllib.request

    import pytest

    playwright = pytest.importorskip("playwright.sync_api")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/flat-ai-queue.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "SEED_DEMO_DATA": "false",
            "PYTHONPATH": str(ROOT),
        })
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/health", timeout=1):
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise AssertionError("Test server not ready")
            with playwright.sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.goto(base + "/signup")
                    page.fill("#name", "AI Queue UI Tester")
                    page.fill("#organization-name", "AI Queue UI Test Workspace")
                    page.fill("#username", "queue.browser.user")
                    page.fill("#signup-email", "queue.browser@example.test")
                    page.fill("#password", "browser-password-123")
                    page.fill("#confirm-password", "browser-password-123")
                    page.click("#submit-button")
                    page.wait_for_url("**/dashboard", timeout=15000)

                    demo = {
                        "totals": {}, "journey": [], "performance": {
                            "people": [], "totals": {},
                            "attention": {
                                "stuck_leads": [
                                    {"id": 101, "name": "Demo Lead", "status": "Contacted"}
                                ],
                                "quotes_needing_follow_up": [
                                    {"id": 202, "name": "Demo Quote", "status": "Draft"}
                                ],
                            },
                        }, "insight": None, "insight_error": "Unavailable in demo",
                    }
                    page.route("**/api/ai/dashboard", lambda route: route.fulfill(
                        status=200, content_type="application/json",
                        body=__import__("json").dumps(demo),
                    ))
                    page.goto(base + "/ai")
                    items = page.locator(".ai-queue-list .ai-queue-row")
                    items.first.wait_for(state="visible", timeout=15000)
                    assert items.count() == 2
                    assert items.nth(0).get_attribute("data-go") == "/leads/101"
                    assert items.nth(1).get_attribute("data-go") == "/quotes/202"
                    assert not page.locator(".ai-queue-list button.related-item").count()
                    styles = items.first.evaluate("""element => {
                        const s = window.getComputedStyle(element);
                        return { borderLeft: s.borderLeftWidth, borderRight: s.borderRightWidth,
                            boxShadow: s.boxShadow, width: element.getBoundingClientRect().width,
                            container: element.parentElement.getBoundingClientRect().width };
                    }""")
                    assert styles["borderLeft"] == styles["borderRight"] == "0px", styles
                    assert styles["boxShadow"] == "none", styles
                    assert abs(styles["width"] - styles["container"]) < 2, styles
                    items.nth(1).click()
                    page.wait_for_url("**/quotes/202", timeout=12000)
                finally:
                    browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
