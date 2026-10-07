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
            "DATABASE_URL": f"sqlite:///{tmp}/tenant-audit.db",
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


def test_tenant_sensitive_model_matrix_is_organization_scoped():
    out = run_app_script("""
    tenant_sensitive = [
        main.Territory, main.SecurityGroup, main.PermissionProfile, main.SharingPolicy,
        main.Teamspace, main.MetadataModule, main.WorkflowExecution,
        main.Lead, main.Account, main.Contact, main.Deal, main.Product, main.Note,
        main.Attachment, main.Email, main.Activity, main.OrganizationSetting,
        main.ApprovalProcess, main.ApprovalRequest, main.Blueprint,
        main.BlueprintTransitionLog, main.ReportRun, main.ApexAssistantRun,
        main.PlatformRecord, main.DocumentBlob, main.AIExceptionOccurrence,
        main.AIExceptionEvent, main.AITaskProposal, main.AITaskOperation,
        main.AuditEvent, main.ImportJob, main.PrivacyRecord,
        main.OwnershipTransfer, main.ApiRequestLog,
    ]
    out['missing'] = [
        model.__name__ for model in tenant_sensitive
        if model.__table__.columns.get('organization_id') is None
    ]
    owner_aware = [
        mapper.class_.__name__
        for mapper in main.Base.registry.mappers
        if hasattr(mapper.class_, 'owner_id')
        and mapper.class_.__table__.columns.get('organization_id') is None
    ]
    out['owner_aware_missing'] = sorted(owner_aware)
    """)
    assert out == {'missing': [], 'owner_aware_missing': []}


def test_read_only_sharing_allows_read_but_denies_write():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Sharing Owner','username':'sharing.owner','email':'sharing.owner@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'sharing.member@example.com'})
        token = invite.json()['invitation_token']
        lead = c.post('/api/leads', json={'name':'Shared Lead'}).json()
        with main.SessionLocal() as db:
            owner = db.scalar(main.select(main.User).where(main.User.email == 'sharing.owner@example.com'))
            org_id = main._organization_id_for_user(db, owner.id)
            db.add(main.SharingPolicy(
                organization_id=org_id,
                name='Read-only CRM sharing',
                module='leads',
                scope='Public Read Only',
                criteria={},
                access='Read Only',
                enabled=True,
            ))
            db.commit()
        c.post('/api/auth/logout')
        c.post('/api/auth/signup', json={
            'name':'Sharing Member','username':'sharing.member','email':'sharing.member@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        out['read'] = c.get(f"/api/leads/{lead['id']}").status_code
        denied = c.patch(f"/api/leads/{lead['id']}", json={'name':'Must not update'})
        out['write'] = denied.status_code
    """)
    assert out == {'read': 200, 'write': 403}


def test_role_hierarchy_can_grant_subordinate_record_access():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Sales Rep','username':'role.rep','email':'role.rep@example.com',
            'password':'strong-password-123'
        })
        invite = c.post('/api/organization/invitations', json={'email':'manager@example.com'})
        token = invite.json()['invitation_token']
        lead = c.post('/api/leads', json={'name':'Rep Owned Lead'}).json()
        with main.SessionLocal() as db:
            rep = db.scalar(main.select(main.User).where(main.User.email == 'role.rep@example.com'))
            org_id = main._organization_id_for_user(db, rep.id)
            db.add_all([
                main.PlatformRecord(
                    organization_id=org_id, owner_id=rep.id, resource='roles',
                    title='Sales manager', status='Active', archived=False,
                    data={'name':'Sales manager','data_scope':'Own and Subordinates','status':'Active'}
                ),
                main.PlatformRecord(
                    organization_id=org_id, owner_id=rep.id, resource='roles',
                    title='Sales rep', status='Active', archived=False,
                    data={'name':'Sales rep','parent_role':'Sales manager','data_scope':'Own','status':'Active'}
                ),
                main.SharingPolicy(
                    organization_id=org_id, name='Role hierarchy', module='leads',
                    scope='Role Hierarchy', criteria={}, access='Read/Write', enabled=True
                )
            ])
            db.commit()
        c.post('/api/auth/logout')
        c.post('/api/auth/signup', json={
            'name':'Manager','username':'role.manager','email':'manager@example.com',
            'password':'strong-password-123','invitation_token':token
        })
        with main.SessionLocal() as db:
            manager = db.scalar(main.select(main.User).where(main.User.email == 'manager@example.com'))
            manager.role = 'Sales manager'
            db.commit()
        # refresh the session actor from DB-backed account
        c.post('/api/auth/logout')
        c.post('/api/auth/login', json={'identifier':'role.manager','password':'strong-password-123'})
        out['read'] = c.get(f"/api/leads/{lead['id']}").status_code
        out['write'] = c.patch(f"/api/leads/{lead['id']}", json={'name':'Manager Updated Lead'}).status_code
    """)
    assert out == {'read': 200, 'write': 200}


def test_existing_empty_workspace_user_can_accept_invitation_safely():
    out = run_app_script("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Target Owner','username':'target.owner','email':'target.owner@example.com',
            'password':'strong-password-123'
        })
        invitation = c.post('/api/organization/invitations', json={'email':'existing@example.com'}).json()
        token = invitation['invitation_token']
        target_org = c.get('/api/organization').json()['id']
        c.post('/api/auth/logout')

        c.post('/api/auth/signup', json={
            'name':'Existing User','username':'existing.user','email':'existing@example.com',
            'password':'strong-password-123'
        })
        before = c.get('/api/organization').json()['id']
        accepted = c.post('/api/organization/invitations/accept', json={'invitation_token':token})
        after = c.get('/api/organization').json()['id']
        out['accepted'] = accepted.status_code
        out['moved'] = before != after and after == target_org
    """)
    assert out == {'accepted': 200, 'moved': True}
