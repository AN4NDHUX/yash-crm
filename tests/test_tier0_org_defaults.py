from __future__ import annotations

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
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "out = {}\n"
        + textwrap.dedent(body)
        + "\nprint('RESULT' + json.dumps(out))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/tenant-defaults.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "platform.owner",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "owner@example.com",
            "ADMIN_NAME": "Platform Owner",
            "PYTHONPATH": str(ROOT),
            "SEED_DEMO_DATA": "false",
        })
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    if result.returncode != 0:
        raise AssertionError(result.stderr[-7000:])
    lines = [line for line in result.stdout.splitlines() if line.startswith("RESULT")]
    if not lines:
        raise AssertionError(result.stdout[-5000:])
    return json.loads(lines[-1][6:])


def test_new_organizations_receive_isolated_default_configuration():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Defaults Org A','username':'defaults.a','email':'defaults.a@example.com',
            'password':'strong-password-123'
        })
        settings_a = c.get('/api/settings/general').json()
        company_a = c.get('/api/platform/company_details').json()
        out['a_settings_id'] = settings_a['id']
        out['a_company_total'] = company_a['total']
        out['a_company_id'] = company_a['items'][0]['id']
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Defaults Org B','username':'defaults.b','email':'defaults.b@example.com',
            'password':'strong-password-123'
        })
        settings_b = c.get('/api/settings/general').json()
        company_b = c.get('/api/platform/company_details').json()
        out['b_settings_id'] = settings_b['id']
        out['b_company_total'] = company_b['total']
        out['b_company_id'] = company_b['items'][0]['id']

        with main.SessionLocal() as db:
            user_a = db.scalar(main.select(main.User).where(main.User.email == 'defaults.a@example.com'))
            user_b = db.scalar(main.select(main.User).where(main.User.email == 'defaults.b@example.com'))
            org_a = main._organization_id_for_user(db, user_a.id)
            org_b = main._organization_id_for_user(db, user_b.id)
            out['different_orgs'] = org_a != org_b
            out['settings_org_a'] = db.get(main.OrganizationSetting, out['a_settings_id']).organization_id
            out['settings_org_b'] = db.get(main.OrganizationSetting, out['b_settings_id']).organization_id
            out['company_org_a'] = db.get(main.PlatformRecord, out['a_company_id']).organization_id
            out['company_org_b'] = db.get(main.PlatformRecord, out['b_company_id']).organization_id
            out['org_a'] = org_a
            out['org_b'] = org_b
    """)
    assert out['different_orgs'] is True
    assert out['a_settings_id'] != out['b_settings_id']
    assert out['a_company_id'] != out['b_company_id']
    assert out['a_company_total'] == 1
    assert out['b_company_total'] == 1
    assert out['settings_org_a'] == out['org_a']
    assert out['settings_org_b'] == out['org_b']
    assert out['company_org_a'] == out['org_a']
    assert out['company_org_b'] == out['org_b']
