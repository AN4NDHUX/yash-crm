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
