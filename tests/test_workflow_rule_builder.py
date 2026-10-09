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
        out['rejected'] = bad.status_code == 422
        out['rejection_detail'] = bad.json().get('detail', '')
    """)
    assert out["function_created"] == 201
    assert out["rule_created"] == 201
    assert out["lead_created"] in (200, 201)
    assert out["company"] == "Normalized Company"
    assert out["executed"]
    assert out["bad_created"] == 422
    assert out["rejected"]
    assert "unsupported action" in out["rejection_detail"]


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


def test_field_change_trigger_only_runs_when_monitored_field_changes():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Field Change Owner','organization_name':'Changed Field Org',
            'username':'field.change.owner','email':'field.change@example.com',
            'password':'strong-password-123'
        })
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Company Change','module':'leads','event':'field_change',
            'trigger_field':'company', 'actions':[{'type':'audit','value':'Company changed'}],
            'status':'Active'
        })
        out['rule_created'] = rule.status_code
        lead = c.post('/api/leads', json={'name':'Trigger Lead','company':'One'})
        lead_id = lead.json()['id']
        c.patch('/api/leads/' + str(lead_id), json={'phone':'12345'})
        before = c.get('/api/automation/executions').json()['items']
        out['before_count'] = len([x for x in before if x['rule_id'] == rule.json()['id']])
        c.patch('/api/leads/' + str(lead_id), json={'company':'Two'})
        after = c.get('/api/automation/executions').json()['items']
        out['after_count'] = len([x for x in after if x['rule_id'] == rule.json()['id']])
    """)
    assert out['rule_created'] == 201
    assert out['before_count'] == 0
    assert out['after_count'] == 1


def test_scheduled_lead_workflow_blocks_early_execution():
    out = app_scenario("""
    from datetime import datetime, timedelta
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Scheduled Owner','organization_name':'Scheduled Org',
            'username':'scheduled.owner','email':'scheduled.owner@example.com',
            'password':'strong-password-123'
        })
        future = (datetime.utcnow() + timedelta(days=1)).isoformat()
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Follow-up Tomorrow','module':'leads','event':'create',
            'scheduled_for':future,
            'actions':[{'type':'create_task','value':'Scheduled follow-up'}],
            'status':'Active'
        })
        lead = c.post('/api/leads', json={'name':'Scheduled Lead','company':'Scheduled Co'})
        executions = c.get('/api/automation/executions').json()['items']
        selected = [x for x in executions if x['rule_id'] == rule.json()['id']]
        out['queued'] = len(selected) == 1 and selected[0]['status'] == 'queued'
        out['early_status'] = c.post('/api/automation/executions/' + str(selected[0]['id']) + '/run').status_code
        out['lead_status'] = lead.status_code
    """)
    assert out['lead_status'] in (200, 201)
    assert out['queued']
    assert out['early_status'] == 409


def test_workflow_owner_assignment_rejects_user_from_another_organization():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Other Owner','organization_name':'Different Workspace',
            'username':'other.workspace.owner','email':'other.workspace@example.com',
            'password':'strong-password-123'
        })
        with main.SessionLocal() as db:
            other_user = db.scalar(main.select(main.User).where(main.User.email == 'other.workspace@example.com'))
            other_id = other_user.id
        c.post('/api/auth/logout')
        c.post('/api/auth/signup', json={
            'name':'Primary Owner','organization_name':'Primary Workspace',
            'username':'primary.workspace.owner','email':'primary.workspace@example.com',
            'password':'strong-password-123'
        })
        own_id = c.get('/api/organization').json()['id']
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Unsafe Owner','module':'leads','event':'create',
            'actions':[{'type':'owner_change','user_id':other_id}],
            'status':'Active'
        })
        lead = c.post('/api/leads', json={'name':'Protected Assignment','company':'Tenant'})
        with main.SessionLocal() as db:
            saved = db.get(main.Lead, lead.json()['id'])
            out['tenant_safe'] = saved.organization_id == own_id and saved.owner_id != other_id
        executions = c.get('/api/automation/executions').json()['items']
        out['rejected'] = any(row['rule_id'] == rule.json()['id'] and row['status'] == 'failed' for row in executions)
        out['rule_status'] = rule.status_code
    """)
    assert out['rule_status'] == 201
    assert out['tenant_safe']
    assert out['rejected']


def test_invalid_workflow_trigger_and_schedule_are_rejected():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Validation Owner','organization_name':'Validation Org',
            'username':'workflow.validation','email':'workflow.validation@example.com',
            'password':'strong-password-123'
        })
        out['missing_field'] = c.post('/api/platform/workflow_rules', json={
            'name':'Missing Watched Field','module':'leads','event':'field_change',
            'actions':[{'type':'audit','value':'test'}],'status':'Active'
        }).status_code
        out['invalid_datetime'] = c.post('/api/platform/workflow_rules', json={
            'name':'Invalid Schedule','module':'leads','event':'create',
            'scheduled_for':'not-a-date', 'actions':[{'type':'audit','value':'test'}],
            'status':'Active'
        }).status_code
    """)
    assert out['missing_field'] == 422
    assert out['invalid_datetime'] == 422


def test_workflow_function_gallery_uses_interactive_creation_and_module_scoping():
    """Prevent regression to a blocking prompt or a stale function dropdown."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] /
              "static/js/features/workflow-rules.js").read_text(encoding="utf-8")
    assert 'data-wf-gallery-create' in source
    assert 'data-wf-function-create' in source
    assert 'Function templates' in source
    assert 'functionPicker ? functionDialog()' in source
    assert 'prompt("Function gallery:' not in source
    assert 'functionRecords = await api("/api/platform/functions?limit=100")' in source
    assert 'fn.associations.modules.includes(draft.module)' in source
    assert 'action.value=String(created.id)' in source


def test_declarative_function_editor_buttons_are_wired():
    """Keep approved function edit, save and cancel actions usable."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] /
              "static/js/features/workflow-rules.js").read_text(encoding="utf-8")
    assert 'data-wf-declarative-name' in source
    assert 'data-wf-declarative-type' in source
    assert 'data-wf-declarative-value' in source
    assert 'data-wf-declarative-save' in source
    assert 'data-wf-declarative-cancel' in source
    assert 'declarativeEditorDialog()' in source
    assert 'method:"PATCH",body:JSON.stringify({name,source:steps,status:"Active"})' in source


def test_workflow_function_picker_empty_state_and_search_buttons():
    """Function picker controls must navigate and search without replacing focused inputs."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] /
              "static/js/features/workflow-rules.js").read_text(encoding="utf-8")
    assert 'data-wf-gallery-create' in source
    assert 'data-wf-function-row' in source
    assert 'row.hidden=' in source
    assert 'data-wf-function-create' in source
    assert 'functionPicker=false;functionEditingId=null;functionDraft=null;functionEditor=true;await refresh(root)' in source
    assert 'data-wf-associate-function' in source
    assert 'functionSearch=event.target.value;await refresh(root)' not in source


def test_python_function_editor_is_fullscreen_and_terminal_styled():
    """Prevent regression to a small textarea modal without editor controls."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] /
              "static/js/features/workflow-rules.js").read_text(encoding="utf-8")
    assert 'height:100dvh' in source
    assert 'width:100vw' in source
    assert 'data-wf-editor-lines' in source
    assert 'data-wf-editor-position' in source
    assert 'data-wf-new-function-source' in source
    assert 'data-wf-editor-save' in source
    assert 'codeInput.addEventListener("keydown"' in source
    assert 'codeInput.setRangeText("    ",start,end,"end")' in source


def test_convos_is_shared_ui_cleanup_preserves_terminal_editor():
    """Global layout rules must not override the full-screen function editor."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    css = (root / "static/css/components.css").read_text(encoding="utf-8")
    app_css = (root / "static/css/app.css").read_text(encoding="utf-8")
    assert '@import url("./components.css")' in app_css
    assert '.wf-rule-overlay:not([style*="padding:0"])' in css
    assert 'overscroll-behavior: contain' in css
    assert 'max-height: calc(100dvh - 24px)' in css
    assert 'overflow-x: auto' in css
    assert ':focus-visible' in css
    assert '@media (max-width: 820px)' in css


def test_fullscreen_function_editor_escapes_transformed_app_container():
    """The code overlay must mount at body level rather than inside the CRM shell."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] /
              "static/js/features/workflow-rules.js").read_text(encoding="utf-8")
    assert 'data-wf-code-portal' in source
    assert 'document.body.appendChild(overlay)' in source
    assert 'document.querySelector("[data-wf-code-portal]")?.remove()' in source
    assert 'width:100%;max-width:none;height:100%' in source
    assert 'grid-template-columns:repeat(auto-fit' in source
