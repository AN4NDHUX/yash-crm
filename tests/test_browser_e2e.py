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

                page.goto(base + "/app/setup/workflow_rules")
                page.locator("[data-wf-create]").wait_for(timeout=12000)
                assert page.locator("[data-platform-create=workflow_rules]").count() == 0
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
                page.locator("[data-wf-edit]").first.wait_for(state="visible", timeout=15000)
                assert page.locator("[data-wf-edit]").count() >= 1
                page.locator("[data-wf-search]").fill("Browser Lead Workflow")
                assert page.locator("[data-wf-edit]").count() >= 1
                page.locator("[data-wf-module-filter]").select_option("leads")
                assert page.locator("[data-wf-edit]").first.is_visible()
                page.locator("[data-wf-edit]").first.click()
                page.locator("[data-wf-name]").wait_for(state="visible", timeout=15000)
                page.locator("[data-wf-name]").fill("Browser Lead Workflow Edited")
                page.locator("[data-wf-next]").click()
                page.locator("[data-wf-event]").wait_for(state="visible", timeout=15000)
                page.locator("[data-wf-next]").click()
                page.locator('input[name="wf-criteria-mode"][value="all"]').wait_for(state="visible", timeout=15000)
                page.locator("[data-wf-next]").click()
                page.locator("[data-wf-action-type='0']").wait_for(state="visible", timeout=15000)
                page.locator("[data-wf-next]").click()
                page.locator("[data-wf-edit]").first.wait_for(state="visible", timeout=15000)
                assert "Edited" in page.locator("[data-wf-edit]").first.inner_text()
                page.locator("[data-wf-delete]").first.wait_for(state="visible", timeout=15000)
                page.once("dialog", lambda dialog: dialog.accept())
                page.locator("[data-wf-delete]").first.click()
                page.wait_for_function("""async () => {
                    const response = await fetch('/api/platform/workflow_rules?limit=100');
                    return response.ok && !(await response.json()).items.some(
                        row => row.name === 'Browser Lead Workflow Edited'
                    );
                }""", timeout=15000)


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


def test_browser_lead_transitions_deal_stage_and_timeline():
    """Exercise real clicks and persisted stage changes in Chromium."""
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/record-stage-browser.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_NAME": "Administrator",
            "SEED_DEMO_DATA": "false",
            "PYTHONPATH": str(ROOT),
        })
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        try:
            wait_for_server(base)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(base + "/signup")
                page.fill("#name", "Stage Browser User")
                page.fill("#organization-name", "Stage Browser Organization")
                page.fill("#username", "stage.browser")
                page.fill("#signup-email", "stage.browser@example.com")
                page.fill("#password", "browser-password-123")
                page.fill("#confirm-password", "browser-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=15000)
                records = page.evaluate("""async () => {
                    const status = await fetch('/api/ai/status');
                    const token = (await status.json()).csrf_token;
                    const create = async (resource, data) => {
                        const r = await fetch('/api/' + resource, {
                            method: 'POST', credentials: 'same-origin',
                            headers: {'Content-Type':'application/json','X-Yash-CSRF':token},
                            body: JSON.stringify(data)
                        });
                        return {status:r.status, data: await r.json()};
                    };
                    return {
                        lead: await create('leads', {name:'Browser Lead Stage'}),
                        deal: await create('deals', {name:'Browser Deal Stage'})
                    };
                }""")
                assert records["lead"]["status"] in (200, 201), records
                assert records["deal"]["status"] in (200, 201), records
                lead_id = records["lead"]["data"]["id"]
                deal_id = records["deal"]["data"]["id"]

                page.goto(base + f"/leads/{lead_id}")
                page.locator('[data-lead-transition][data-status="Contacted"]').wait_for()
                assert page.get_by_text("Customer journey").count() == 0
                page.locator('[data-lead-transition][data-status="Contacted"]').click()
                page.wait_for_function("""async id => {
                    const r = await fetch('/api/leads/' + id);
                    return r.ok && (await r.json()).status === 'Contacted';
                }""", arg=lead_id)
                page.locator('.crm-state-current strong').filter(has_text="Contacted").wait_for(timeout=12000)
                page.locator('[data-detail-tab="timeline"]').click()
                page.locator('[data-timeline-kind="history"]').wait_for()
                assert page.get_by_text("Status changed from New to Contacted").count() >= 1
                page.locator('[data-timeline-kind="interactions"]').click()
                assert page.locator('[data-timeline-content="interactions"]').is_visible()
                page.locator('[data-timeline-kind="history"]').click()

                page.goto(base + f"/deals/{deal_id}")
                page.locator('[data-stage-update][data-stage="Proposal"]').wait_for()
                page.locator('[data-stage-update][data-stage="Proposal"]').click()
                page.wait_for_function("""async id => {
                    const r = await fetch('/api/deals/' + id);
                    return r.ok && (await r.json()).stage === 'Proposal';
                }""", arg=deal_id)
                page.locator('.crm-pipeline-step.is-current').filter(has_text="Proposal").wait_for(timeout=12000)
                assert "Proposal" in page.locator('.crm-pipeline-step.is-current').inner_text()
                page.locator('[data-detail-tab="timeline"]').click()
                assert page.get_by_text("Stage changed from Qualification to Proposal").count() >= 1
                browser.close()
        finally:
            server.terminate()
            try:
                server.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate(timeout=5)


def test_browser_blueprint_connect_states_and_publish():
    """Click-to-connect and drag-to-connect must persist real Blueprint edges."""
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/blueprint-canvas.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_NAME": "Administrator",
            "SEED_DEMO_DATA": "false",
            "PYTHONPATH": str(ROOT),
        })
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        try:
            wait_for_server(base)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1500, "height": 920})
                page.goto(base + "/signup")
                page.fill("#name", "Visual Canvas Owner")
                page.fill("#organization-name", "Visual Canvas Organization")
                page.fill("#username", "visual.canvas")
                page.fill("#signup-email", "visual.canvas@example.com")
                page.fill("#password", "browser-password-123")
                page.fill("#confirm-password", "browser-password-123")
                page.click("#submit-button")
                page.wait_for_url("**/dashboard", timeout=15000)

                page.goto(base + "/setup/blueprints")
                page.locator('[data-bp-open="new"]').wait_for(timeout=15000)
                page.locator('[data-bp-open="new"]').click()
                page.locator('[data-bp-details] input[name="name"]').fill("Browser Connected Process")
                field_select = page.locator('[data-bp-details] select[name="field_name"]')
                assert field_select.locator('option').count() >= 8
                assert field_select.locator('option[value="email"]').is_disabled()
                field_select.select_option("source")
                page.locator('[data-bp-details] button[type="submit"]').click()
                page.locator('[data-bp-add-state="Website"]').wait_for(timeout=12000)
                page.locator('[data-bp="back"]').click()
                page.locator('[data-bp-details] select[name="field_name"]').select_option("status")
                page.locator('[data-bp="add-condition"]').click()
                condition = page.locator('[data-bp-condition="0"]')
                condition.locator('select[name="field"]').select_option("status")
                values = condition.locator('select[name="value_choice"]')
                assert "Contacted" in values.locator("option").all_text_contents()
                values.select_option("New")
                assert condition.locator('select[name="value_choice"]').input_value() == "New"
                condition.locator('select[name="field"]').select_option("company")
                values = condition.locator('select[name="value_choice"]')
                assert "＋ Enter custom value" in values.locator("option").all_text_contents()
                values.select_option("__custom__")
                condition.locator('input[name="value_custom"]').fill("Custom Enterprise")
                assert condition.locator('input[name="value_custom"]').is_visible()
                # Restore a real picklist value and ensure the custom-input mode clears.
                condition.locator('select[name="field"]').select_option("status")
                condition.locator('select[name="value_choice"]').select_option("New")
                page.locator('[data-bp-details] button[type="submit"]').click()
                page.locator('[data-bp-canvas]').wait_for()
                for label in ("New", "Contacted", "Qualified"):
                    page.locator(f'[data-bp-add-state="{label}"]').click()
                assert page.locator(".bp-node").count() == 3

                # Click a source connector and then a destination node.
                page.locator('[data-bp-connect="0"]').click()
                page.locator('.bp-node[data-bp-state="1"]').click()
                assert page.locator(".bp-edge-label").count() == 1
                assert page.locator(".bp-edge-label").first.inner_text() == "Move to Contacted"
                page.locator("[data-bp-edge-label]").fill("Establish contact")
                page.locator("[data-bp-edge-label]").press("Tab")

                # Drag from the second state's connection handle onto the third state.
                source = page.locator('[data-bp-connect="1"]').bounding_box()
                target = page.locator('.bp-node[data-bp-state="2"]').bounding_box()
                assert source and target
                page.mouse.move(source["x"] + source["width"]/2, source["y"] + source["height"]/2)
                page.mouse.down()
                page.mouse.move(target["x"] + target["width"]/2, target["y"] + target["height"]/2, steps=12)
                page.mouse.up()
                assert page.locator(".bp-edge-label").count() == 2
                assert page.locator(".bp-edge-path").count() == 2

                page.locator('[data-bp="save"]').click()
                page.locator('[data-bp-row]').filter(has_text="Browser Connected Process").wait_for()
                page.locator('[data-bp-row]').filter(has_text="Browser Connected Process").locator("[data-bp-open]").click()
                page.locator('[data-bp-details] button[type="submit"]').click()
                page.locator(".bp-edge-label").first.wait_for()
                assert page.locator(".bp-edge-label").count() == 2
                page.locator('[data-bp="publish"]').click()

                page.wait_for_function("""async () => {
                    const res = await fetch('/api/blueprint-designer');
                    return res.ok && (await res.json()).items.some(item =>
                        item.name === 'Browser Connected Process' && item.active &&
                        !item.draft && item.entry_conditions.length === 1 &&
                        item.entry_conditions[0].field === 'status' &&
                        item.entry_conditions[0].value === 'New' &&
                        item.transitions.length === 2 &&
                        item.transitions[0].label === 'Establish contact' &&
                        item.transitions[0].from === 'New' &&
                        item.transitions[0].to === 'Contacted' &&
                        item.transitions[1].from === 'Contacted' &&
                        item.transitions[1].to === 'Qualified');
                }""", timeout=15000)
                browser.close()
        finally:
            server.terminate()
            try:
                server.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate(timeout=5)
