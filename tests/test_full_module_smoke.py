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


def test_dashboard_survives_legacy_sales_platform_json_shapes():
    out = run_app_script("""
    with TestClient(main.app) as c:
        with main.SessionLocal() as db:
            admin = db.scalar(main.select(main.User).where(main.func.lower(main.User.role) == 'administrator').order_by(main.User.id))
            org_id = main._organization_id_for_user(db, admin.id)
            token_actor = main.TENANT_ACTOR_ID.set(admin.id)
            token_org = main.TENANT_ORGANIZATION_ID.set(org_id)
            try:
                db.add_all([
                    main.PlatformRecord(
                        organization_id=org_id,
                        owner_id=admin.id,
                        resource='sales_targets',
                        title='Legacy target',
                        status='Active',
                        data=['bad-target-shape'],
                        archived=False,
                    ),
                    main.PlatformRecord(
                        organization_id=org_id,
                        owner_id=admin.id,
                        resource='payments',
                        title='Legacy payment',
                        status='Received',
                        amount=100,
                        data='bad-payment-shape',
                        archived=False,
                    ),
                    main.PlatformRecord(
                        organization_id=org_id,
                        owner_id=admin.id,
                        resource='quotes',
                        title='Legacy quote',
                        status='Sent',
                        amount=1000,
                        data=12345,
                        archived=False,
                    ),
                ])
                db.commit()
            finally:
                main.TENANT_ORGANIZATION_ID.reset(token_org)
                main.TENANT_ACTOR_ID.reset(token_actor)

        response = c.get('/api/dashboard', headers=auth)
        out['status'] = response.status_code
        if response.status_code == 200:
            payload = response.json()
            out['has_metrics'] = isinstance(payload.get('metrics'), dict)
            out['has_attention'] = isinstance(payload.get('attention'), dict)
    """)
    assert out == {'status': 200, 'has_metrics': True, 'has_attention': True}


def test_malformed_profile_json_cannot_take_down_all_modules():
    out = run_app_script("""
    with TestClient(main.app) as c:
        with main.SessionLocal() as db:
            admin = db.scalar(main.select(main.User).where(main.func.lower(main.User.role) == 'administrator').order_by(main.User.id))
            org_id = main._organization_id_for_user(db, admin.id)
            admin.profile_name = 'Legacy Broken Profile'
            token_actor = main.TENANT_ACTOR_ID.set(admin.id)
            token_org = main.TENANT_ORGANIZATION_ID.set(org_id)
            try:
                db.add(main.PlatformRecord(
                    organization_id=org_id,
                    owner_id=admin.id,
                    resource='profiles',
                    title='Legacy Broken Profile',
                    status='Active',
                    data=['invalid-profile-json'],
                    archived=False,
                ))
                db.commit()
            finally:
                main.TENANT_ORGANIZATION_ID.reset(token_org)
                main.TENANT_ACTOR_ID.reset(token_actor)

        failures = {}
        paths = [
            '/api/dashboard',
            '/api/leads?limit=1',
            '/api/contacts?limit=1',
            '/api/accounts?limit=1',
            '/api/deals?limit=1',
            '/api/activities?limit=1',
            '/api/products?limit=1',
            '/api/platform/vendors?limit=1',
            '/api/platform/payments?limit=1',
            '/api/platform/reports?limit=1',
        ]
        for path in paths:
            response = c.get(path, headers=auth)
            if response.status_code >= 500:
                failures[path] = [response.status_code, response.text[:300]]
        out['failures'] = failures
    """)
    assert out['failures'] == {}


def test_every_visible_module_avoids_500_with_legacy_security_records():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Module Audit User',
            'username':'module.audit',
            'email':'module.audit@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = signup.status_code

        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'module.audit@example.com'))
            org_id = main._organization_id_for_user(db, user.id)
            user.role = 'Sales rep'
            user.profile_name = 'Legacy Profile'
            token_actor = main.TENANT_ACTOR_ID.set(user.id)
            token_org = main.TENANT_ORGANIZATION_ID.set(org_id)
            try:
                db.add_all([
                    main.PlatformRecord(
                        organization_id=org_id,
                        owner_id=user.id,
                        resource='roles',
                        title='Sales rep',
                        status='Active',
                        data=['invalid-role-json'],
                        archived=False,
                    ),
                    main.PlatformRecord(
                        organization_id=org_id,
                        owner_id=user.id,
                        resource='profiles',
                        title='Legacy Profile',
                        status='Active',
                        data='invalid-profile-json',
                        archived=False,
                    ),
                ])
                db.commit()
            finally:
                main.TENANT_ORGANIZATION_ID.reset(token_org)
                main.TENANT_ACTOR_ID.reset(token_actor)

        endpoints = {
            'dashboard': '/api/dashboard',
            'teamspaces': '/api/teamspaces',
            'leads': '/api/leads?limit=1',
            'contacts': '/api/contacts?limit=1',
            'accounts': '/api/accounts?limit=1',
            'deals': '/api/deals?limit=1',
            'tasks': '/api/activities?activity_type=Task&limit=1',
            'meetings': '/api/activities?activity_type=Meeting&limit=1',
            'calls': '/api/activities?activity_type=Call&limit=1',
            'products': '/api/products?limit=1',
            'price_books': '/api/platform/price_books?limit=1',
            'vendors': '/api/platform/vendors?limit=1',
            'quotes': '/api/platform/quotes?limit=1',
            'sales_orders': '/api/platform/sales_orders?limit=1',
            'purchase_orders': '/api/platform/purchase_orders?limit=1',
            'invoices': '/api/platform/invoices?limit=1',
            'payments': '/api/platform/payments?limit=1',
            'campaigns': '/api/platform/campaigns?limit=1',
            'cases': '/api/platform/cases?limit=1',
            'solutions': '/api/platform/solutions?limit=1',
            'documents': '/api/platform/documents?limit=1',
            'site_visits': '/api/platform/site_visits?limit=1',
            'forecasts': '/api/platform/forecasts?limit=1',
            'reports': '/api/platform/reports?limit=1',
            'dashboards': '/api/platform/dashboards?limit=1',
            'sales_targets': '/api/platform/sales_targets?limit=1',
            'meta': '/api/meta',
            'catalog': '/api/platform/catalog',
            'settings': '/api/settings/general',
            'profile': '/api/settings/profile',
            'ai_status': '/api/ai/status',
        }
        failures = {}
        statuses = {}
        for name, path in endpoints.items():
            response = c.get(path)
            statuses[name] = response.status_code
            if response.status_code >= 500:
                failures[name] = [response.status_code, response.text[:500]]
        out['failures'] = failures
        out['statuses'] = statuses
    """)
    assert out['signup'] == 201
    assert out['failures'] == {}


def test_every_populated_module_lists_for_normal_tenant_user_without_500():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Populated Module User',
            'username':'populated.audit',
            'email':'populated.audit@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = signup.status_code

        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'populated.audit@example.com'))
            org_id = main._organization_id_for_user(db, user.id)
            user.role = 'Sales rep'
            user.profile_name = 'Standard'

            subscription = main._ensure_organization_subscription(db, user)
            plan = db.scalar(main.select(main.Plan).where(main.func.lower(main.Plan.code) == 'crm_plus'))
            if plan is not None:
                subscription.plan_id = plan.id
                subscription.status = 'Active'

            token_actor = main.TENANT_ACTOR_ID.set(user.id)
            token_org = main.TENANT_ORGANIZATION_ID.set(org_id)
            try:
                account = main.Account(organization_id=org_id, owner_id=user.id, name='Audit Account', status='Active')
                contact = main.Contact(organization_id=org_id, owner_id=user.id, first_name='Audit', last_name='Contact')
                lead = main.Lead(organization_id=org_id, owner_id=user.id, name='Audit Lead', company='Audit Co', status='New')
                deal = main.Deal(organization_id=org_id, owner_id=user.id, name='Audit Deal', stage='Qualification', status='Open', amount=1000)
                activity = main.Activity(organization_id=org_id, owner_id=user.id, activity_type='Task', subject='Audit Task', status='Open')
                product = main.Product(organization_id=org_id, owner_id=user.id, name='Audit Product', status='Active')
                db.add_all([account, contact, lead, deal, activity, product])

                for resource in main.PLATFORM_RESOURCES:
                    db.add(main.PlatformRecord(
                        organization_id=org_id,
                        owner_id=user.id,
                        resource=resource,
                        title=f'Audit {resource}',
                        status='Active',
                        data={'name': f'Audit {resource}'},
                        archived=False,
                    ))

                db.commit()
            finally:
                main.TENANT_ORGANIZATION_ID.reset(token_org)
                main.TENANT_ACTOR_ID.reset(token_actor)

        endpoints = {
            'dashboard': '/api/dashboard',
            'teamspaces': '/api/teamspaces',
            'leads': '/api/leads?limit=100',
            'contacts': '/api/contacts?limit=100',
            'accounts': '/api/accounts?limit=100',
            'deals': '/api/deals?limit=100',
            'tasks': '/api/activities?activity_type=Task&limit=100',
            'meetings': '/api/activities?activity_type=Meeting&limit=100',
            'calls': '/api/activities?activity_type=Call&limit=100',
            'products': '/api/products?limit=100',
        }
        for resource in main.PLATFORM_RESOURCES:
            endpoints[f'platform:{resource}'] = f'/api/platform/{resource}?limit=100'

        failures = {}
        statuses = {}
        totals = {}
        for name, path in endpoints.items():
            response = c.get(path)
            statuses[name] = response.status_code
            if response.status_code >= 500:
                failures[name] = [response.status_code, response.text[:1000]]
                continue
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict) and 'total' in payload:
                    totals[name] = payload.get('total')

        out['failures'] = failures
        out['statuses'] = statuses
        out['totals'] = totals
    """)
    assert out['signup'] == 201
    assert out['failures'] == {}
    for resource in ['leads','contacts','accounts','deals','tasks','products']:
        assert out['statuses'][resource] == 200
        assert out['totals'][resource] >= 1


def test_populated_modules_survive_malformed_field_metadata():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Metadata Audit User',
            'username':'metadata.audit',
            'email':'metadata.audit@example.com',
            'password':'strong-password-123'
        })
        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'metadata.audit@example.com'))
            org_id = main._organization_id_for_user(db, user.id)
            token_actor = main.TENANT_ACTOR_ID.set(user.id)
            token_org = main.TENANT_ORGANIZATION_ID.set(org_id)
            try:
                module = main.MetadataModule(
                    organization_id=org_id,
                    owner_id=user.id,
                    api_name='leads',
                    label='Leads',
                    plural_label='Leads',
                    enabled=True,
                )
                db.add(module)
                db.flush()
                db.add(main.MetadataField(
                    module_id=module.id,
                    api_name='legacy_broken_field',
                    label='Broken legacy field',
                    field_type='text',
                    visibility=['bad-visibility'],
                    permissions='bad-permissions',
                ))
                db.add(main.Lead(
                    organization_id=org_id,
                    owner_id=user.id,
                    name='Metadata Audit Lead',
                    company='Audit',
                    status='New',
                ))
                db.commit()
            finally:
                main.TENANT_ORGANIZATION_ID.reset(token_org)
                main.TENANT_ACTOR_ID.reset(token_actor)

        response = c.get('/api/leads?limit=100')
        out['status'] = response.status_code
        out['body'] = response.text[:500]
    """)
    assert out['status'] == 200, out
