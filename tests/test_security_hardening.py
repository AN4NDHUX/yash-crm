from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_app_script(body: str, **env_overrides: str) -> dict:
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
            "DATABASE_URL": f"sqlite:///{tmp}/security.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_NAME": "Administrator",
            "PYTHONPATH": str(ROOT),
        })
        env.update(env_overrides)
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


def test_normal_account_cannot_administer_users_or_security():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        created = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Standard User','username':'standard.user','email':'standard@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = created.status_code
        with main.SessionLocal() as db:
            admin = db.scalar(main.select(main.User).where(main.func.lower(main.User.role) == 'administrator').order_by(main.User.id))
            out['report_users'] = None
            try:
                main._report_rows(db, 'users')
            except main.HTTPException as exc:
                out['report_users'] = exc.status_code
        out['users'] = c.get('/api/users').status_code
        out['security'] = c.get('/api/security/overview').status_code
        out['patch_admin'] = c.patch(f"/api/users/{admin.id}", json={'role':'Administrator'}).status_code
    """)
    assert out == {
        'signup': 201,
        'report_users': 422,
        'users': 403,
        'security': 403,
        'patch_admin': 403,
    }


def test_login_rate_limit_triggers():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        codes = []
        for _ in range(11):
            codes.append(c.post('/api/auth/login', json={
                'identifier':'rate-limit@example.com',
                'password':'wrong-password-123'
            }).status_code)
        out['codes'] = codes
    """)
    assert out['codes'][:10] == [401] * 10
    assert out['codes'][10] == 429


def test_password_login_creates_session_without_otp():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        response = c.post('/api/auth/login', json={
            'identifier':'admin',
            'password':'supersecretpass123'
        })
        payload = response.json()
        out['status'] = response.status_code
        out['ok'] = payload.get('ok')
        out['redirect'] = payload.get('redirect')
        out['session'] = c.get('/api/auth/session').status_code
        out['otp_route_present'] = any(
            getattr(route, 'path', None) == '/api/auth/login/verify-otp'
            for route in main.app.routes
        )
    """)
    assert out == {
        'status': 200,
        'ok': True,
        'redirect': '/dashboard',
        'session': 200,
        'otp_route_present': False,
    }


def test_security_headers_and_no_duplicate_routes():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        response = c.get('/login')
        out['csp'] = response.headers.get('content-security-policy', '')
        out['coop'] = response.headers.get('cross-origin-opener-policy', '')
        pairs = []
        for route in main.app.routes:
            path = getattr(route, 'path', None)
            methods = getattr(route, 'methods', None) or []
            for method in methods:
                pairs.append(method + ' ' + str(path))
        out['logout_routes'] = pairs.count('POST /api/auth/logout')
        out['uploads_mount'] = any(getattr(route, 'path', None) == '/uploads' for route in main.app.routes)
    """)
    assert "default-src 'self'" in out['csp']
    assert out['coop'] == 'same-origin'
    assert out['logout_routes'] == 1
    assert out['uploads_mount'] is False


def test_password_policy_requires_eight_characters():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        short = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Short Password','username':'short.password','email':'short@example.com',
            'password':'1234567'
        })
        valid = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Valid Password','username':'valid.password','email':'valid@example.com',
            'password':'12345678'
        })
        out['short'] = short.status_code
        out['valid'] = valid.status_code
    """)
    assert out == {'short': 422, 'valid': 201}


def test_document_download_is_tenant_authorized_and_database_backed():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Document Owner','username':'doc.owner','email':'doc.owner@example.com',
            'password':'strong-password-123'
        })
        uploaded = c.post(
            '/api/documents/upload',
            data={'name':'Private document'},
            files={'file':('private.txt', b'private tenant content', 'text/plain')},
        )
        out['upload'] = uploaded.status_code
        item = uploaded.json()
        out['url'] = item.get('url')
        item_id = item['id']
        own = c.get(f'/api/documents/{item_id}/download')
        out['own'] = own.status_code
        out['body'] = own.content.decode()
        with main.SessionLocal() as db:
            out['blob_count'] = int(db.scalar(main.select(main.func.count()).select_from(main.DocumentBlob)) or 0)
        c.post('/api/auth/logout')
        second = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Other Tenant','username':'other.tenant','email':'other.tenant@example.com',
            'password':'strong-password-123'
        })
        out['second_signup'] = second.status_code
        if second.status_code != 201:
            login = c.post('/api/auth/login', json={
                'identifier':'other.tenant',
                'password':'strong-password-123'
            })
            out['second_login'] = login.status_code
        else:
            out['second_login'] = 200
        out['cross_tenant'] = c.get(f'/api/documents/{item_id}/download').status_code
    """)
    assert out['upload'] == 201
    assert out['url'].endswith('/download')
    assert out['own'] == 200
    assert out['body'] == 'private tenant content'
    assert out['blob_count'] == 1
    assert out['second_signup'] == 201
    assert out['second_login'] == 200
    assert out['cross_tenant'] == 404


def test_ready_exposes_release_evidence_without_secrets():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        response = c.get('/ready')
        payload = response.json()
        out['status'] = response.status_code
        out['service'] = payload.get('service')
        out['database'] = payload.get('database')
        out['app_revision'] = payload.get('app_revision')
        out['has_migration_revision'] = 'migration_revision' in payload
    """, APP_REVISION="tier0-test-revision")
    assert out == {
        'status': 200,
        'service': 'yash-crm',
        'database': 'ready',
        'app_revision': 'tier0-test-revision',
        'has_migration_revision': True,
    }
