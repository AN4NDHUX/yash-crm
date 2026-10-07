from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_app_script(body: str) -> dict:
    script = (
        "import base64, json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "from app.platform_catalog import PLATFORM_RESOURCES\n"
        "token = base64.b64encode(b'admin:supersecretpass123').decode()\n"
        "auth = {'Authorization': 'Basic ' + token}\n"
        "out = {}\n" + textwrap.dedent(body) + "\nprint('RESULT' + json.dumps(out, default=str))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/test.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "PYTHONPATH": str(ROOT),
        })
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise AssertionError(result.stderr[-5000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[6:])


def test_all_core_and_platform_module_list_apis_respond():
    out = run_app_script("""
    with TestClient(main.app) as c:
        failures = {}
        for resource in ['leads','contacts','accounts','deals','activities','products']:
            r = c.get(f'/api/{resource}?limit=1', headers=auth)
            if r.status_code != 200:
                failures[f'core:{resource}'] = [r.status_code, r.text[:200]]
        for resource in PLATFORM_RESOURCES:
            r = c.get(f'/api/platform/{resource}?limit=1', headers=auth)
            if r.status_code != 200:
                failures[f'platform:{resource}'] = [r.status_code, r.text[:200]]
        out['failures'] = failures
    """)
    assert out["failures"] == {}


def test_critical_administration_and_ai_surfaces_respond():
    out = run_app_script("""
    with TestClient(main.app) as c:
        paths = [
            '/api/platform/catalog',
            '/api/settings/general',
            '/api/settings/profile',
            '/api/users?limit=1',
            '/api/audit?limit=1',
            '/api/administration/recycle-bin?limit=1',
            '/api/ai/status',
            '/api/ai/exceptions/readiness',
            '/api/admin/metadata/modules',
        ]
        failures = {}
        for path in paths:
            r = c.get(path, headers=auth)
            if r.status_code != 200:
                failures[path] = [r.status_code, r.text[:200]]
        out['failures'] = failures
    """)
    assert out["failures"] == {}


def test_payments_and_invoice_lookup_survive_legacy_platform_json_shapes():
    out = run_app_script("""
    with TestClient(main.app) as c:
        with main.SessionLocal() as db:
            admin = db.scalar(main.select(main.User).where(main.func.lower(main.User.role) == 'administrator').order_by(main.User.id))
            org_id = main._organization_id_for_user(db, admin.id)
            token_actor = main.TENANT_ACTOR_ID.set(admin.id)
            token_org = main.TENANT_ORGANIZATION_ID.set(org_id)
            try:
                invoice = main.PlatformRecord(
                    organization_id=org_id,
                    owner_id=admin.id,
                    resource='invoices',
                    title='Legacy invoice',
                    status='Issued',
                    amount=1000,
                    data=['legacy', 'invoice'],
                    archived=False,
                )
                payment = main.PlatformRecord(
                    organization_id=org_id,
                    owner_id=admin.id,
                    resource='payments',
                    title='Legacy payment',
                    status='Received',
                    amount=500,
                    data='legacy-payment-json',
                    archived=False,
                )
                db.add_all([invoice, payment])
                db.commit()
            finally:
                main.TENANT_ORGANIZATION_ID.reset(token_org)
                main.TENANT_ACTOR_ID.reset(token_actor)

        invoices = c.get('/api/platform/invoices?limit=100&sort=name_asc', headers=auth)
        payments = c.get('/api/platform/payments?limit=100&sort=updated_desc', headers=auth)
        out['invoice_status'] = invoices.status_code
        out['payment_status'] = payments.status_code
        out['invoice_items'] = len(invoices.json().get('items', [])) if invoices.status_code == 200 else None
        out['payment_items'] = len(payments.json().get('items', [])) if payments.status_code == 200 else None
    """)
    assert out['invoice_status'] == 200
    assert out['payment_status'] == 200
    assert out['invoice_items'] >= 1
    assert out['payment_items'] >= 1
