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
            "DATABASE_URL": f"sqlite:///{tmp}/tenant.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_NAME": "Administrator",
            "PYTHONPATH": str(ROOT),
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
        raise AssertionError(result.stderr[-5000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[6:])


def test_new_accounts_start_empty_and_existing_account_restores_owned_data():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        a = c.post('/api/auth/signup', json={
            'name':'User One','username':'user.one','email':'one@example.com',
            'phone':'+919900001111','password':'12345678'
        })
        out['signup_a'] = a.status_code
        out['a_initial'] = c.get('/api/dashboard').json()['metrics']
        lead = c.post('/api/leads', json={'name':'Private Lead','company':'Tenant One'})
        out['lead_a'] = lead.status_code
        out['a_leads_after_create'] = c.get('/api/leads').json()['total']
        module = c.post('/api/admin/metadata/modules', json={
            'label':'Private Module','api_name':'private_module','plural_label':'Private Modules'
        })
        out['module_a'] = module.status_code
        out['a_modules'] = c.get('/api/admin/metadata/modules').json()['total']
        c.post('/api/auth/logout')

        b = c.post('/api/auth/signup', json={
            'name':'User Two','username':'user.two','email':'two@example.com',
            'phone':'+919900002222','password':'abcdefgh'
        })
        out['signup_b'] = b.status_code
        out['b_dashboard'] = c.get('/api/dashboard').json()['metrics']
        out['b_leads'] = c.get('/api/leads').json()['total']
        out['b_modules'] = c.get('/api/admin/metadata/modules').json()['total']
        c.post('/api/auth/logout')

        login_a = c.post('/api/auth/login', json={'identifier':'one@example.com','password':'12345678'})
        out['login_a'] = login_a.status_code
        out['a_restored_leads'] = c.get('/api/leads').json()['total']
        out['a_restored_modules'] = c.get('/api/admin/metadata/modules').json()['total']
    """)
    assert out['signup_a'] == 201
    assert out['a_initial']['total_leads'] == 0
    assert out['a_initial']['open_deals'] == 0
    assert out['a_initial']['pipeline_value'] == 0
    assert out['a_initial']['activities_due'] == 0
    assert out['lead_a'] == 200
    assert out['a_leads_after_create'] == 1
    assert out['module_a'] == 201
    assert out['a_modules'] == 1
    assert out['signup_b'] == 201
    assert out['b_dashboard']['total_leads'] == 0
    assert out['b_dashboard']['open_deals'] == 0
    assert out['b_dashboard']['pipeline_value'] == 0
    assert out['b_dashboard']['activities_due'] == 0
    assert out['b_leads'] == 0
    assert out['b_modules'] == 0
    assert out['login_a'] == 200
    assert out['a_restored_leads'] == 1
    assert out['a_restored_modules'] == 1


def test_duplicate_email_phone_and_username_are_rejected_and_8_char_password_is_valid():
    out = run_app_script("""
    with TestClient(main.app) as c:
        first = c.post('/api/auth/signup', json={
            'name':'Unique User','username':'unique.user','email':'unique@example.com',
            'phone':'+919811112222','password':'12345678'
        })
        c.post('/api/auth/logout')
        same_email = c.post('/api/auth/signup', json={
            'name':'Other','username':'other.one','email':'unique@example.com',
            'phone':'+919811113333','password':'abcdefgh'
        })
        same_phone = c.post('/api/auth/signup', json={
            'name':'Other','username':'other.two','email':'other2@example.com',
            'phone':'+919811112222','password':'abcdefgh'
        })
        same_username = c.post('/api/auth/signup', json={
            'name':'Other','username':'unique.user','email':'other3@example.com',
            'phone':'+919811114444','password':'abcdefgh'
        })
        short_password = c.post('/api/auth/signup', json={
            'name':'Short Password','username':'short.pass','email':'short@example.com',
            'password':'1234567'
        })
        out.update({
            'first': first.status_code,
            'same_email': same_email.status_code,
            'same_phone': same_phone.status_code,
            'same_username': same_username.status_code,
            'short_password': short_password.status_code,
        })
    """)
    assert out == {
        'first': 201,
        'same_email': 409,
        'same_phone': 409,
        'same_username': 409,
        'short_password': 422,
    }


def test_account_events_create_in_app_notifications():
    out = run_app_script("""
    with TestClient(main.app) as c:
        created = c.post('/api/auth/signup', json={
            'name':'Notify User','username':'notify.user','email':'notify@example.com',
            'phone':'+919822223333','password':'12345678'
        })
        notifications = c.get('/api/notifications?limit=20').json()['items']
        c.post('/api/auth/logout')
        logged = c.post('/api/auth/login', json={'identifier':'+919822223333','password':'12345678'})
        notifications2 = c.get('/api/notifications?limit=20').json()['items']
        out['created'] = created.status_code
        out['logged'] = logged.status_code
        out['kinds1'] = [x['kind'] for x in notifications]
        out['kinds2'] = [x['kind'] for x in notifications2]
    """)
    assert out['created'] == 201
    assert out['logged'] == 200
    assert 'account_created' in out['kinds1']
    assert 'login' in out['kinds2']
