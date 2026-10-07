from __future__ import annotations

import hashlib
import hmac
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
        "import hashlib, hmac, json\n"
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
            "DATABASE_URL": f"sqlite:///{tmp}/tier0-completion.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "platform.owner",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "owner@example.com",
            "ADMIN_NAME": "Platform Owner",
            "PYTHONPATH": str(ROOT),
            "SEED_DEMO_DATA": "false",
            "RAZORPAY_WEBHOOK_SECRET": "tier0-webhook-secret",
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


def test_invited_user_joins_same_organization_and_other_tenant_is_isolated():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        a = c.post('/api/auth/signup', json={
            'name':'Org Owner','username':'org.owner','email':'org.owner@example.com',
            'password':'strong-password-123'
        })
        out['a_signup'] = a.status_code
        invite = c.post('/api/organization/invitations', json={
            'email':'member@example.com','membership_role':'Member'
        })
        out['invite'] = invite.status_code
        token = invite.json()['invitation_token']
        org_a = c.get('/api/organization').json()['id']
        c.post('/api/auth/logout')

        b = c.post('/api/auth/signup', json={
            'name':'Org Member','username':'org.member','email':'member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        out['b_signup'] = b.status_code
        org_b = c.get('/api/organization').json()['id']
        out['same_org'] = org_a == org_b
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={
            'name':'Other Tenant','username':'other.tenant','email':'other@example.com',
            'password':'strong-password-123'
        })
        other_org = c.get('/api/organization').json()['id']
        out['different_org'] = other_org != org_a

        with main.SessionLocal() as db:
            owner = db.scalar(main.select(main.User).where(main.User.email == 'org.owner@example.com'))
            org_id = main._organization_id_for_user(db, owner.id)
            lead = main.Lead(name='Org Private Lead', owner_id=owner.id, organization_id=org_id)
            db.add(lead)
            db.commit()
            out['lead_id'] = lead.id

        out['cross_tenant_get'] = c.get(f"/api/leads/{out['lead_id']}").status_code
    """)
    assert out['a_signup'] == 201
    assert out['invite'] == 201
    assert out['b_signup'] == 201
    assert out['same_org'] is True
    assert out['different_org'] is True
    assert out['cross_tenant_get'] == 404


def test_record_limit_is_shared_across_organization_members():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Quota Owner','username':'quota.owner','email':'quota.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'quota.member@example.com'})
        token = invite.json()['invitation_token']
        with main.SessionLocal() as db:
            free = db.scalar(main.select(main.Plan).where(main.Plan.code == 'free'))
            free.max_records = 1
            db.commit()
        first = c.post('/api/leads', json={'name':'First shared record'})
        out['first'] = first.status_code
        c.post('/api/auth/logout')
        c.post('/api/auth/signup', json={
            'name':'Quota Member','username':'quota.member','email':'quota.member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        second = c.post('/api/leads', json={'name':'Second shared record'})
        out['second'] = second.status_code
        out['code'] = (second.json().get('detail') or {}).get('code')
    """)
    assert out == {'first': 200, 'second': 403, 'code': 'PLAN_RECORD_LIMIT'}


def test_profile_denial_is_enforced_at_api_boundary():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Profile User','username':'profile.user','email':'profile@example.com',
            'password':'strong-password-123'
        })
        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'profile@example.com'))
            org_id = main._organization_id_for_user(db, user.id)
            profile = main.PlatformRecord(
                resource='profiles', title='Restricted Seller', status='Active',
                owner_id=user.id, organization_id=org_id, archived=False,
                data={'name':'Restricted Seller','permissions':{'leads':{'read':True,'create':False,'update':False}}}
            )
            db.add(profile)
            user.profile_name = 'Restricted Seller'
            db.commit()
        denied = c.post('/api/leads', json={'name':'Must be blocked'})
        out['status'] = denied.status_code
        out['code'] = (denied.json().get('detail') or {}).get('code')
        allowed = c.get('/api/leads')
        out['read'] = allowed.status_code
    """)
    assert out == {'status': 403, 'code': 'PROFILE_PERMISSION_DENIED', 'read': 200}


def test_field_level_write_permission_is_enforced():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Field User','username':'field.user','email':'field@example.com',
            'password':'strong-password-123'
        })
        lead = c.post('/api/leads', json={'name':'Field Security Lead','email':'before@example.com'}).json()
        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'field@example.com'))
            org_id = main._organization_id_for_user(db, user.id)
            module = main.MetadataModule(
                api_name='leads', label='Leads', plural_label='Leads',
                owner_id=user.id, organization_id=org_id, enabled=True, config={}
            )
            db.add(module)
            db.flush()
            db.add(main.MetadataField(
                module_id=module.id, api_name='email', label='Email', field_type='email',
                position=1, required=False, read_only=False, unique_value=False,
                permissions={'sales rep': {'write': False}}, visibility={}
            ))
            db.commit()
        denied = c.patch(f"/api/leads/{lead['id']}", json={'email':'after@example.com'})
        out['status'] = denied.status_code
        out['code'] = (denied.json().get('detail') or {}).get('code')
    """)
    assert out == {'status': 403, 'code': 'FIELD_PERMISSION_DENIED'}


def test_signed_billing_webhook_is_required_and_idempotent():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Paid User','username':'paid.user','email':'paid@example.com',
            'password':'strong-password-123'
        })
        request = c.patch('/api/subscription', json={'plan_code':'professional'}).json()
        request_id = request['request_id']
        out['before'] = c.get('/api/plans').json()['current_subscription']['plan_code']
        body = json.dumps({
            'event':'payment_link.paid',
            'payload':{'payment_link':{'entity':{
                'id':'plink_tier0',
                'reference_id':f'yash-upgrade-{request_id}'
            }}}
        }, separators=(',', ':')).encode()
        bad = c.post('/api/billing/webhook/razorpay', content=body, headers={
            'content-type':'application/json','x-razorpay-signature':'bad'
        })
        out['bad'] = bad.status_code
        signature = hmac.new(b'tier0-webhook-secret', body, hashlib.sha256).hexdigest()
        good = c.post('/api/billing/webhook/razorpay', content=body, headers={
            'content-type':'application/json','x-razorpay-signature':signature
        })
        duplicate = c.post('/api/billing/webhook/razorpay', content=body, headers={
            'content-type':'application/json','x-razorpay-signature':signature
        })
        out['good'] = good.status_code
        out['duplicate'] = duplicate.json().get('duplicate')
        out['after'] = c.get('/api/plans').json()['current_subscription']['plan_code']
        with main.SessionLocal() as db:
            out['events'] = int(db.scalar(main.select(main.func.count()).select_from(main.BillingWebhookEvent)) or 0)
    """)
    assert out == {
        'before': 'free',
        'bad': 400,
        'good': 200,
        'duplicate': True,
        'after': 'professional',
        'events': 1,
    }
