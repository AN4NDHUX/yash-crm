from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
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


def totp(secret: str) -> str:
    cleaned = secret.replace(" ", "").upper()
    padding = "=" * ((8 - len(cleaned) % 8) % 8)
    key = base64.b32decode(cleaned + padding, casefold=True)
    counter = int(time.time() // 30)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def test_normal_account_cannot_administer_users_or_security():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        created = c.post('/api/auth/signup', json={
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


def test_admin_totp_is_enforced_when_configured():
    secret = "JBSWY3DPEHPK3PXP"
    code = totp(secret)
    out = run_app_script(f"""
    with TestClient(main.app, follow_redirects=False) as c:
        missing = c.post('/api/auth/login', json={{
            'identifier':'admin','password':'supersecretpass123'
        }})
        good = c.post('/api/auth/login', json={{
            'identifier':'admin','password':'supersecretpass123','otp':'{code}'
        }})
        out['missing'] = missing.status_code
        out['missing_code'] = missing.json().get('detail', {{}}).get('code')
        out['good'] = good.status_code
    """, YASHCRM_ADMIN_TOTP_SECRET=secret)
    assert out == {'missing': 401, 'missing_code': 'MFA_REQUIRED', 'good': 200}


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


def test_password_policy_requires_twelve_characters():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        short = c.post('/api/auth/signup', json={
            'name':'Short Password','username':'short.password','email':'short@example.com',
            'password':'12345678901'
        })
        valid = c.post('/api/auth/signup', json={
            'name':'Valid Password','username':'valid.password','email':'valid@example.com',
            'password':'123456789012'
        })
        out['short'] = short.status_code
        out['valid'] = valid.status_code
    """)
    assert out == {'short': 422, 'valid': 201}
