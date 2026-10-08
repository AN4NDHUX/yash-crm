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


def test_organization_rename_requires_membership_and_preserves_tenant_identity():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        a = c.post('/api/auth/signup', json={
            'name':'Rename Owner A', 'organization_name':'Original Workspace A',
            'username':'rename.owner.a', 'email':'rename.a@example.com',
            'password':'strong-password-123'
        })
        out['signup_a'] = a.status_code
        original = c.get('/api/organization').json()
        out['original_id'] = original['id']
        out['original_slug'] = original['slug']
        renamed = c.patch('/api/organization', json={'name':'Renamed Workspace A'})
        out['rename_status'] = renamed.status_code
        out['rename_name'] = renamed.json().get('name')
        out['settings_name'] = c.get('/api/settings/general').json()['org_name']
        out['same_id'] = c.get('/api/organization').json()['id'] == original['id']
        out['same_slug'] = c.get('/api/organization').json()['slug'] == original['slug']
        out['invalid_status'] = c.patch('/api/organization', json={'name':' '}).status_code
        c.post('/api/auth/logout')
        b = c.post('/api/auth/signup', json={
            'name':'Rename Owner B', 'organization_name':'Original Workspace B',
            'username':'rename.owner.b', 'email':'rename.b@example.com',
            'password':'strong-password-123'
        })
        out['signup_b'] = b.status_code
        out['other_org_name'] = c.get('/api/organization').json()['name']
        out['other_org_id'] = c.get('/api/organization').json()['id']
        c.post('/api/auth/logout')
        out['unauthorized_status'] = c.patch('/api/organization', json={'name':'Unauthorized'}).status_code
    """)
    assert out['signup_a'] == out['signup_b'] == 201
    assert out['rename_status'] == 200
    assert out['rename_name'] == out['settings_name'] == 'Renamed Workspace A'
    assert out['same_id'] and out['same_slug']
    assert out['invalid_status'] == 422
    assert out['other_org_name'] == 'Original Workspace B'
    assert out['other_org_id'] != out['original_id']
    assert out['unauthorized_status'] == 401


def test_ownership_transfer_requires_current_owner_and_same_tenant_member():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Transfer Owner', 'organization_name':'Transfer Workspace',
            'username':'transfer.owner', 'email':'transfer.owner@example.com',
            'password':'strong-password-123'
        })
        original_org = c.get('/api/organization').json()['id']
        with main.SessionLocal() as db:
            original_user = db.scalar(main.select(main.User).where(main.User.email == 'transfer.owner@example.com'))
            original_id = original_user.id
        invite = c.post('/api/organization/invitations', json={
            'email':'transfer.member@example.com', 'membership_role':'Member'
        })
        token = invite.json()['invitation_token']
        out['missing_target'] = c.post('/api/organization/transfer-ownership', json={'user_id':999999}).status_code
        c.post('/api/auth/logout')
        c.post('/api/auth/signup', json={
            'name':'Transfer Member', 'username':'transfer.member',
            'email':'transfer.member@example.com',
            'password':'strong-password-123', 'invitation_token':token
        })
        with main.SessionLocal() as db:
            member = db.scalar(main.select(main.User).where(main.User.email == 'transfer.member@example.com'))
            member_id = member.id
        out['member_forbidden'] = c.post('/api/organization/transfer-ownership', json={'user_id':original_id}).status_code
        c.post('/api/auth/logout')
        c.post('/api/auth/login', json={'identifier':'transfer.owner','password':'strong-password-123'})
        changed = c.post('/api/organization/transfer-ownership', json={'user_id':member_id})
        out['transfer_status'] = changed.status_code
        out['new_owner_id'] = changed.json().get('owner_user_id')
        out['old_owner_role'] = c.get('/api/organization').json()['membership_role']
        out['repeat_forbidden'] = c.post('/api/organization/transfer-ownership', json={'user_id':member_id}).status_code
        with main.SessionLocal() as db:
            out['persisted_owner'] = db.get(main.Organization, original_org).owner_user_id
        c.post('/api/auth/logout')
        c.post('/api/auth/login', json={'identifier':'transfer.member','password':'strong-password-123'})
        out['new_owner_role'] = c.get('/api/organization').json()['membership_role']
        out['organization_unchanged'] = c.get('/api/organization').json()['id'] == original_org
    """)
    assert out['missing_target'] == 404
    assert out['member_forbidden'] == 403
    assert out['transfer_status'] == 200
    assert out['new_owner_id'] == out['persisted_owner']
    assert out['old_owner_role'] == 'Admin'
    assert out['new_owner_role'] == 'Owner'
    assert out['organization_unchanged']
    assert out['repeat_forbidden'] == 403
