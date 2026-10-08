from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def app_scenario(body: str) -> dict:
    script = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "from app.services.core import workflow_criteria_match\n"
        "out = {}\n"
        + textwrap.dedent(body)
        + "\nprint('RESULT' + json.dumps(out, default=str))\n"
    )
    with tempfile.TemporaryDirectory() as directory:
        env = {
            **os.environ,
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{directory}/workflow.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123",
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_NAME": "Administrator",
            "SEED_DEMO_DATA": "false",
            "PYTHONPATH": str(ROOT),
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
    assert result.returncode == 0, result.stderr[-6500:]
    lines = [line for line in result.stdout.splitlines() if line.startswith("RESULT")]
    assert lines, result.stdout[-2500:]
    return json.loads(lines[-1][6:])


def test_zoho_style_nested_condition_operators():
    out = app_scenario("""
    source = {'website':'https://example.com','amount':1500,'email':'sales@example.com'}
    out['matching'] = workflow_criteria_match(source, {
        'logic':'AND','conditions':[
            {'field':'website','operator':'contains','value':'example'},
            {'field':'website','operator':'starts_with','value':'https://'},
            {'field':'website','operator':'ends_with','value':'.com'},
            {'field':'email','operator':'does_not_contain','value':'other'},
            {'logic':'OR','conditions':[
                {'field':'amount','operator':'greater_than','value':1000},
                {'field':'amount','operator':'less_than','value':5}
            ]}
        ]
    })
    out['not_matching'] = workflow_criteria_match(source, {
        'field':'website','operator':'does_not_contain','value':'example'
    })
    """)
    assert out["matching"] is True
    assert out["not_matching"] is False


def test_workflow_rule_builder_persists_trigger_and_runs_on_create_and_edit():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Workflow Owner','organization_name':'Workflow Test Org',
            'username':'workflow.owner','email':'workflow.owner@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = signup.status_code
        payload = {
            'name':'Website Rule',
            'description':'Notify CRM on matching website',
            'module':'leads',
            'event':'create_or_edit',
            'criteria':{'logic':'AND','conditions':[{'field':'company','operator':'contains','value':'example'}]},
            'actions':[{'type':'audit','value':'Website qualified'}],
            'status':'Active'
        }
        added = c.post('/api/platform/workflow_rules', json=payload)
        out['create_status'] = added.status_code
        out['saved_trigger'] = added.json().get('event')
        out['saved_description'] = added.json().get('description')
        out['stored_actions'] = added.json().get('actions')
        created = c.post('/api/leads', json={
            'name':'Workflow Lead', 'company':'example Acme'
        })
        out['lead_create'] = created.status_code
        lead_id = created.json().get('id')
        modified = c.patch('/api/leads/' + str(lead_id), json={'company':'example Partners'})
        out['lead_edit'] = modified.status_code
        executions = c.get('/api/automation/executions').json()
        out['executions'] = [x['event'] for x in executions.get('items',[]) if x.get('rule_id') == added.json().get('id')]
        out['statuses'] = [x['status'] for x in executions.get('items',[]) if x.get('rule_id') == added.json().get('id')]
    """)
    assert out["signup"] == 201
    assert out["create_status"] == 201
    assert out["saved_trigger"] == "create_or_edit"
    assert out["saved_description"] == "Notify CRM on matching website"
    assert out["stored_actions"][0]["type"] == "audit"
    assert out["lead_create"] in (200, 201)
    assert out["lead_edit"] == 200
    assert "create" in out["executions"]
    assert "update" in out["executions"]
    assert all(status == "completed" for status in out["statuses"])


def test_workflow_field_update_cannot_change_tenant_identity():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Tenant Workflow Owner', 'organization_name':'Safe Tenant',
            'username':'tenant.workflow.owner', 'email':'tenant.workflow@example.com',
            'password':'strong-password-123'
        })
        original_org_id = c.get('/api/organization').json()['id']
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Blocked Tenant Update', 'module':'leads', 'event':'create',
            'actions':[{'type':'field_update','field':'organization_id','value':999999}],
            'status':'Active'
        })
        out['rule_status'] = rule.status_code
        lead = c.post('/api/leads', json={'name':'Protected Lead','company':'Safety'})
        out['lead_status'] = lead.status_code
        with main.SessionLocal() as db:
            persisted = db.get(main.Lead, lead.json()['id'])
            out['tenant_unchanged'] = persisted.organization_id == original_org_id
        executions = c.get('/api/automation/executions').json()
        out['blocked'] = any(
            x['rule_id'] == rule.json()['id'] and x['status'] == 'failed'
            for x in executions['items']
        )
    """)
    assert out["rule_status"] == 201
    assert out["lead_status"] in (200, 201)
    assert out["tenant_unchanged"]
    assert out["blocked"]



def test_custom_function_executes_field_update_and_blocks_unapproved_steps():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Function Owner', 'organization_name':'Function Test Org',
            'username':'function.owner', 'email':'function.owner@example.com',
            'password':'strong-password-123'
        })
        function = c.post('/api/platform/functions', json={
            'name':'Normalize Lead','runtime':'Python','entrypoint':'steps',
            'source':[{'type':'field_update','field':'company','value':'Normalized Company'}],
            'status':'Active'
        })
        out['function_created'] = function.status_code
        fn_id = function.json().get('id')
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Apply Normalization','module':'leads','event':'create',
            'actions':[{'type':'function','value':str(fn_id)}],'status':'Active'
        })
        out['rule_created'] = rule.status_code
        lead = c.post('/api/leads', json={'name':'Example Lead','company':'Original'})
        out['lead_created'] = lead.status_code
        out['company'] = c.get('/api/leads/' + str(lead.json()['id'])).json().get('company')
        executions = c.get('/api/automation/executions').json()['items']
        out['executed'] = any(e['rule_id'] == rule.json()['id'] and e['status'] == 'completed' for e in executions)
        bad = c.post('/api/platform/functions', json={
            'name':'Unsafe Function','runtime':'Python','entrypoint':'steps',
            'source':[{'type':'function','value':str(fn_id)}], 'status':'Active'
        })
        out['bad_created'] = bad.status_code
        bad_rule = c.post('/api/platform/workflow_rules', json={
            'name':'Reject Nested','module':'leads','event':'create',
            'actions':[{'type':'function','value':str(bad.json()['id'])}],'status':'Active'
        })
        c.post('/api/leads', json={'name':'Blocked Lead','company':'Original'})
        statuses = c.get('/api/automation/executions').json()['items']
        out['rejected'] = any(e['rule_id'] == bad_rule.json()['id'] and e['status'] == 'failed' for e in statuses)
    """)
    assert out["function_created"] == 201
    assert out["rule_created"] == 201
    assert out["lead_created"] in (200, 201)
    assert out["company"] == "Normalized Company"
    assert out["executed"]
    assert out["bad_created"] == 201
    assert out["rejected"]


def test_workflow_rule_edit_preserves_conditions_and_updates_trigger():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Rule Editor','organization_name':'Rule Edit Workspace',
            'username':'rule.editor','email':'rule.editor@example.com',
            'password':'strong-password-123'
        })
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Original Lead Rule','module':'leads','event':'create',
            'criteria':{'logic':'OR','conditions':[
                {'field':'company','operator':'contains','value':'Example'},
                {'field':'email','operator':'ends_with','value':'example.org'}
            ]},
            'actions':[{'type':'audit','value':'Original'}],'status':'Active'
        })
        out['created'] = rule.status_code
        updated = c.patch('/api/platform/workflow_rules/' + str(rule.json()['id']), json={
            'name':'Edited Lead Rule','event':'create_or_edit',
            'actions':[{'type':'audit','value':'Edited'}]
        })
        out['updated'] = updated.status_code
        record = c.get('/api/platform/workflow_rules/' + str(rule.json()['id'])).json()
        out['name'] = record.get('name')
        out['event'] = record.get('event')
        out['criteria'] = record.get('criteria')
        out['action'] = record.get('actions',[{}])[0].get('value')
    """)
    assert out['created'] == 201
    assert out['updated'] == 200
    assert out['name'] == 'Edited Lead Rule'
    assert out['event'] == 'create_or_edit'
    assert out['criteria']['logic'] == 'OR'
    assert len(out['criteria']['conditions']) == 2
    assert out['action'] == 'Edited'
