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
        a = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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

        b = c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Org Member','username':'org.member','email':'member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        out['b_signup'] = b.status_code
        org_b = c.get('/api/organization').json()['id']
        out['same_org'] = org_a == org_b
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
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


def test_advanced_analytics_is_plan_gated():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Analytics User','username':'analytics.user','email':'analytics@example.com',
            'password':'strong-password-123'
        })
        denied = c.get('/api/analytics/sales-performance')
        out['free_status'] = denied.status_code
        out['free_code'] = (denied.json().get('detail') or {}).get('code')

        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'analytics@example.com'))
            subscription = main._ensure_organization_subscription(db, user)
            professional = db.scalar(main.select(main.Plan).where(main.Plan.code == 'professional'))
            subscription.plan_id = professional.id
            subscription.status = 'Active'
            db.commit()

        allowed = c.get('/api/analytics/sales-performance')
        out['professional_status'] = allowed.status_code
    """)
    assert out == {
        'free_status': 403,
        'free_code': 'PLAN_UPGRADE_REQUIRED',
        'professional_status': 200,
    }


def test_cross_organization_user_admin_is_blocked():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Admin A','username':'admin.a','email':'admin.a@example.com',
            'password':'strong-password-123'
        })
        with main.SessionLocal() as db:
            admin_a = db.scalar(main.select(main.User).where(main.User.email == 'admin.a@example.com'))
            admin_a.role = 'Administrator'
            db.commit()
            out['admin_a_id'] = admin_a.id
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'User B','username':'user.b','email':'user.b@example.com',
            'password':'strong-password-123'
        })
        with main.SessionLocal() as db:
            user_b = db.scalar(main.select(main.User).where(main.User.email == 'user.b@example.com'))
            out['user_b_id'] = user_b.id
        c.post('/api/auth/logout')

        c.post('/api/auth/login', json={'identifier':'admin.a','password':'strong-password-123'})
        listed = c.get('/api/users?limit=100')
        out['listed_status'] = listed.status_code
        out['listed_ids'] = sorted(item['id'] for item in listed.json()['items'])
        out['generic_detail'] = c.get(f"/api/users/{out['user_b_id']}").status_code
        out['admin_patch'] = c.patch(f"/api/admin/users/{out['user_b_id']}", json={'role':'Administrator'}).status_code
        out['admin_history'] = c.get(f"/api/admin/users/{out['user_b_id']}/login-history").status_code
    """)
    assert out['listed_status'] == 200
    assert out['listed_ids'] == [out['admin_a_id']]
    assert out['generic_detail'] == 404
    assert out['admin_patch'] == 404
    assert out['admin_history'] == 404


def test_approval_actor_id_payload_cannot_impersonate_approver():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Request Owner','username':'request.owner','email':'request.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'approver@example.com'})
        token = invite.json()['invitation_token']
        with main.SessionLocal() as db:
            owner = db.scalar(main.select(main.User).where(main.User.email == 'request.owner@example.com'))
            org_id = main._organization_id_for_user(db, owner.id)
            enterprise = db.scalar(main.select(main.Plan).where(main.Plan.code == 'enterprise'))
            subscription = main._ensure_organization_subscription(db, owner)
            subscription.plan_id = enterprise.id
            subscription.status = 'Active'
            db.commit()
        lead = c.post('/api/leads', json={'name':'Approval Lead'}).json()
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Real Approver','username':'real.approver','email':'approver@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        with main.SessionLocal() as db:
            approver = db.scalar(main.select(main.User).where(main.User.email == 'approver@example.com'))
            approver.role = 'Sales manager'
            org_id = main._organization_id_for_user(db, approver.id)
            process = main.ApprovalProcess(
                organization_id=org_id,
                name='Tier0 approval',
                module='Leads',
                trigger='Always',
                approver='Sales manager',
                status='Active',
                conditions=[],
                steps=[{'order':1,'approver_id':approver.id,'approver':'Sales manager'}],
            )
            db.add(process)
            db.commit()
            out['approver_id'] = approver.id
            out['process_id'] = process.id
        c.post('/api/auth/logout')

        c.post('/api/auth/login', json={'identifier':'request.owner','password':'strong-password-123'})
        submitted = c.post('/api/approvals/requests', json={
            'process_id':out['process_id'],'resource':'leads','record_id':lead['id']
        })
        out['submit'] = submitted.status_code
        request_id = submitted.json()['id']
        impersonation = c.post(f"/api/approvals/requests/{request_id}/approve", json={
            'actor_id':out['approver_id'],'comment':'impersonated'
        })
        out['impersonation_status'] = impersonation.status_code
        out['impersonation_code'] = (impersonation.json().get('detail') or {}).get('code')
        c.post('/api/auth/logout')

        c.post('/api/auth/login', json={'identifier':'real.approver','password':'strong-password-123'})
        approved = c.post(f"/api/approvals/requests/{request_id}/approve", json={'comment':'approved by session user'})
        out['approved'] = approved.status_code
        out['final_status'] = approved.json().get('status')
    """)
    assert out['submit'] == 201
    assert out['impersonation_status'] == 403
    assert out['impersonation_code'] == 'APPROVER_NOT_AUTHORIZED'
    assert out['approved'] == 200
    assert out['final_status'] == 'Approved'


def test_global_search_respects_private_record_sharing():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Search Owner','username':'search.owner','email':'search.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'search.peer@example.com'})
        token = invite.json()['invitation_token']
        lead = c.post('/api/leads', json={'name':'SecretPeerLeadXYZ'}).json()
        out['lead_id'] = lead['id']
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Search Peer','username':'search.peer','email':'search.peer@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        search = c.get('/api/search?q=SecretPeerLeadXYZ')
        out['search_status'] = search.status_code
        out['found'] = any(item.get('id') == out['lead_id'] and item.get('resource') == 'leads' for item in search.json().get('results', []))
        out['direct'] = c.get(f"/api/leads/{out['lead_id']}").status_code
    """)
    assert out['search_status'] == 200
    assert out['found'] is False
    assert out['direct'] == 404


def test_approval_snapshot_redacts_hidden_fields_for_approver():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Snapshot Owner','username':'snapshot.owner','email':'snapshot.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'snapshot.approver@example.com'})
        token = invite.json()['invitation_token']
        with main.SessionLocal() as db:
            owner = db.scalar(main.select(main.User).where(main.User.email == 'snapshot.owner@example.com'))
            org_id = main._organization_id_for_user(db, owner.id)
            enterprise = db.scalar(main.select(main.Plan).where(main.Plan.code == 'enterprise'))
            subscription = main._ensure_organization_subscription(db, owner)
            subscription.plan_id = enterprise.id
            subscription.status = 'Active'
            db.commit()
        lead = c.post('/api/leads', json={'name':'Snapshot Lead','email':'secret-snapshot@example.com'}).json()
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Snapshot Approver','username':'snapshot.approver','email':'snapshot.approver@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        with main.SessionLocal() as db:
            approver = db.scalar(main.select(main.User).where(main.User.email == 'snapshot.approver@example.com'))
            approver.role = 'Sales manager'
            approver.profile_name = 'Restricted Approver'
            org_id = main._organization_id_for_user(db, approver.id)
            module = main.MetadataModule(
                api_name='leads', label='Leads', plural_label='Leads',
                owner_id=approver.id, organization_id=org_id, enabled=True, config={}
            )
            db.add(module)
            db.flush()
            db.add(main.MetadataField(
                module_id=module.id, api_name='email', label='Email', field_type='email',
                position=1, required=False, read_only=False, unique_value=False,
                permissions={}, visibility={'restricted approver':'hidden'}
            ))
            process = main.ApprovalProcess(
                organization_id=org_id,
                name='Snapshot Approval',
                module='Leads',
                trigger='Always',
                approver='Sales manager',
                status='Active',
                conditions=[],
                steps=[{'order':1,'approver_id':approver.id,'approver':'Sales manager'}],
            )
            db.add(process)
            db.commit()
            out['process_id'] = process.id
        c.post('/api/auth/logout')

        c.post('/api/auth/login', json={'identifier':'snapshot.owner','password':'strong-password-123'})
        submitted = c.post('/api/approvals/requests', json={
            'process_id':out['process_id'],'resource':'leads','record_id':lead['id']
        })
        out['submit'] = submitted.status_code
        request_id = submitted.json()['id']
        c.post('/api/auth/logout')

        c.post('/api/auth/login', json={'identifier':'snapshot.approver','password':'strong-password-123'})
        detail = c.get(f"/api/approvals/requests/{request_id}")
        out['detail'] = detail.status_code
        snapshot = detail.json().get('snapshot') or {}
        out['email_present'] = 'email' in snapshot
        out['name'] = snapshot.get('name')
    """)
    assert out['submit'] == 201
    assert out['detail'] == 200
    assert out['email_present'] is False
    assert out['name'] == 'Snapshot Lead'


def test_cpq_catalog_respects_product_field_security():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'CPQ Owner','username':'cpq.owner','email':'cpq.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'cpq.member@example.com'})
        token = invite.json()['invitation_token']
        with main.SessionLocal() as db:
            owner = db.scalar(main.select(main.User).where(main.User.email == 'cpq.owner@example.com'))
            org_id = main._organization_id_for_user(db, owner.id)
            enterprise = db.scalar(main.select(main.Plan).where(main.Plan.code == 'enterprise'))
            subscription = main._ensure_organization_subscription(db, owner)
            subscription.plan_id = enterprise.id
            subscription.status = 'Active'
            db.commit()
        product = c.post('/api/products', json={'name':'Secure Product','sku':'SEC-001','unit_price':9999,'status':'Active'}).json()
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'CPQ Member','username':'cpq.member','email':'cpq.member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        with main.SessionLocal() as db:
            member = db.scalar(main.select(main.User).where(main.User.email == 'cpq.member@example.com'))
            member.profile_name = 'Restricted Seller'
            org_id = main._organization_id_for_user(db, member.id)
            module = main.MetadataModule(
                api_name='products', label='Products', plural_label='Products',
                owner_id=member.id, organization_id=org_id, enabled=True, config={}
            )
            db.add(module)
            db.flush()
            db.add(main.MetadataField(
                module_id=module.id, api_name='unit_price', label='Unit Price', field_type='currency',
                position=1, required=False, read_only=False, unique_value=False,
                permissions={}, visibility={'restricted seller':'hidden'}
            ))
            db.commit()
        catalog = c.get('/api/cpq/catalog')
        out['status'] = catalog.status_code
        products = catalog.json().get('products', []) if catalog.status_code == 200 else []
        secure = next((item for item in products if item.get('id') == product['id']), None)
        out['product_visible'] = secure is not None
        out['price_present'] = bool(secure and 'unit_price' in secure)
    """)
    assert out == {'status': 200, 'product_visible': True, 'price_present': False}


def test_sensitive_administration_and_automation_routes_require_org_admin():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Boundary Owner','username':'boundary.owner','email':'boundary.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'boundary.member@example.com'})
        token = invite.json()['invitation_token']

        with main.SessionLocal() as db:
            owner = db.scalar(main.select(main.User).where(main.User.email == 'boundary.owner@example.com'))
            org_id = main._organization_id_for_user(db, owner.id)
            blueprint = main.Blueprint(
                organization_id=org_id, name='Private Blueprint', module='Deals',
                entry_criteria='Always', stages=['Qualification','Proposal'],
                transitions=[], transition_requirements=[], active=True
            )
            execution = main.WorkflowExecution(
                organization_id=org_id, rule_id=0, resource='cases', record_id=0,
                event='manual', status='queued', actions=[],
                idempotency_key='tier0-boundary-execution'
            )
            db.add_all([blueprint, execution])
            db.commit()
            out['blueprint_id'] = blueprint.id
            out['execution_id'] = execution.id

        out['owner_recycle'] = c.get('/api/administration/recycle-bin').status_code
        out['owner_duplicates'] = c.get('/api/administration/duplicates?resource=leads').status_code
        out['owner_exec_list'] = c.get('/api/automation/executions').status_code
        out['owner_blueprint'] = c.get(f"/api/blueprints/{out['blueprint_id']}/transitions").status_code
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Boundary Member','username':'boundary.member','email':'boundary.member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        out['member_recycle'] = c.get('/api/administration/recycle-bin').status_code
        out['member_duplicates'] = c.get('/api/administration/duplicates?resource=leads').status_code
        out['member_restore'] = c.post('/api/administration/restore', json={'resource':'leads','record_id':999999}).status_code
        out['member_exec_list'] = c.get('/api/automation/executions').status_code
        out['member_exec_run'] = c.post(f"/api/automation/executions/{out['execution_id']}/run").status_code
        out['member_blueprint'] = c.get(f"/api/blueprints/{out['blueprint_id']}/transitions").status_code
    """)
    assert out['owner_recycle'] == 200
    assert out['owner_duplicates'] == 200
    assert out['owner_exec_list'] == 200
    assert out['owner_blueprint'] == 200
    assert out['member_recycle'] == 403
    assert out['member_duplicates'] == 403
    assert out['member_restore'] == 403
    assert out['member_exec_list'] == 403
    assert out['member_exec_run'] == 403
    assert out['member_blueprint'] == 403


def test_archived_platform_record_restore_respects_private_sharing():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Restore Owner','username':'restore.owner','email':'restore.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'restore.member@example.com'})
        token = invite.json()['invitation_token']
        created = c.post('/api/platform/cases', json={'name':'Private Restore Case','status':'New'})
        out['create'] = created.status_code
        case_id = created.json()['id']
        out['archive'] = c.delete(f'/api/platform/cases/{case_id}').status_code
        out['owner_restore'] = c.post(f'/api/platform/cases/{case_id}/restore').status_code
        c.delete(f'/api/platform/cases/{case_id}')
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={"organization_name": "Automated Test Organization", 
            'name':'Restore Member','username':'restore.member','email':'restore.member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        denied = c.post(f'/api/platform/cases/{case_id}/restore')
        out['member_restore'] = denied.status_code
    """)
    assert out == {
        'create': 201,
        'archive': 200,
        'owner_restore': 200,
        'member_restore': 403,
    }
