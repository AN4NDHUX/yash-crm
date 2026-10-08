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
            "DATABASE_URL": f"sqlite:///{tmp}/tier0.db",
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
        raise AssertionError(result.stderr[-5000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[6:])


def test_signup_creates_organization_owned_free_subscription():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        response = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Tier Zero User',
            'username':'tier.zero',
            'email':'tier.zero@example.com',
            'password':'strong-password-123',
        })
        out['signup'] = response.status_code
        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'tier.zero@example.com'))
            org = main._organization_for_user(db, user.id)
            subscription = main._ensure_organization_subscription(db, user)
            plan = db.get(main.Plan, subscription.plan_id)
            out['org_exists'] = org is not None
            out['org_owner'] = org.owner_user_id == user.id
            out['plan'] = plan.code
            out['legacy_count'] = int(db.scalar(main.select(main.func.count()).select_from(main.Subscription).where(main.Subscription.user_id == user.id)) or 0)
    """)
    assert out == {
        'signup': 201,
        'org_exists': True,
        'org_owner': True,
        'plan': 'free',
        'legacy_count': 0,
    }


def test_paid_plan_selection_creates_pending_request_without_granting_entitlement():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Billing User',
            'username':'billing.user',
            'email':'billing@example.com',
            'password':'strong-password-123',
        })
        before = c.get('/api/plans').json()['current_subscription']
        response = c.patch('/api/subscription', json={'plan_code':'professional'})
        payload = response.json()
        after = c.get('/api/plans').json()['current_subscription']
        out['status'] = response.status_code
        out['before'] = before['plan_code']
        out['after'] = after['plan_code']
        out['requires_payment'] = payload.get('requires_payment')
        out['pending'] = after.get('pending_upgrade', {}).get('plan_code')
        with main.SessionLocal() as db:
            out['pending_count'] = int(db.scalar(main.select(main.func.count()).select_from(main.SubscriptionChangeRequest)) or 0)
    """)
    assert out == {
        'status': 200,
        'before': 'free',
        'after': 'free',
        'requires_payment': True,
        'pending': 'professional',
        'pending_count': 1,
    }


def test_customer_administrator_no_longer_bypasses_plan_entitlements():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Customer Admin',
            'username':'customer.admin',
            'email':'customer.admin@example.com',
            'password':'strong-password-123',
        })
        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'customer.admin@example.com'))
            user.role = 'Administrator'
            db.commit()
            plan = main._active_plan(db, user)
            out['customer_admin_plan'] = plan.code if plan else None
            owner = db.scalar(main.select(main.User).where(main.User.username == 'platform.owner'))
            out['owner_bypass'] = main._active_plan(db, owner) is None
    """)
    assert out == {
        'customer_admin_plan': 'free',
        'owner_bypass': True,
    }


def test_duplicate_paid_selection_reuses_pending_request():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Repeat Request',
            'username':'repeat.request',
            'email':'repeat@example.com',
            'password':'strong-password-123',
        })
        first = c.patch('/api/subscription', json={'plan_code':'standard'}).json()
        second = c.patch('/api/subscription', json={'plan_code':'standard'}).json()
        out['same_request'] = first['request_id'] == second['request_id']
        with main.SessionLocal() as db:
            out['count'] = int(db.scalar(main.select(main.func.count()).select_from(main.SubscriptionChangeRequest)) or 0)
    """)
    assert out == {'same_request': True, 'count': 1}
