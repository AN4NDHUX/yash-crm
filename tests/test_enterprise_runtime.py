from __future__ import annotations

import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_app_script(body: str) -> dict:
    script = (
        "import base64, json\n"
        "from datetime import date, datetime, timedelta\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
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
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stderr[-4000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[6:])


def test_custom_module_runtime_enforces_metadata_and_layout_rules():
    out = run_app_script("""
    with TestClient(main.app) as c:
        module = c.post('/api/admin/metadata/modules', headers=auth, json={
            'api_name':'projects','label':'Project','plural_label':'Projects','config':{'record_name_field':'project_name'}
        }).json()
        c.post(f"/api/admin/metadata/modules/{module['id']}/fields", headers=auth, json={'api_name':'project_name','label':'Project Name','field_type':'text','required':True,'unique_value':True})
        c.post(f"/api/admin/metadata/modules/{module['id']}/fields", headers=auth, json={'api_name':'budget','label':'Budget','field_type':'currency','validation':{'min':0}})
        c.post(f"/api/admin/metadata/modules/{module['id']}/fields", headers=auth, json={'api_name':'status_detail','label':'Status Detail','field_type':'text'})
        c.post(f"/api/admin/metadata/modules/{module['id']}/layouts", headers=auth, json={'name':'Standard','rules':[{'criteria':[{'field':'budget','operator':'>','value':1000}],'actions':[{'type':'required','field':'status_detail'}]}]})
        bad = c.post('/api/custom/projects', headers=auth, json={'project_name':'Alpha','budget':2000})
        good = c.post('/api/custom/projects', headers=auth, json={'project_name':'Alpha','budget':2000,'status_detail':'Approved'})
        dup = c.post('/api/custom/projects', headers=auth, json={'project_name':'Alpha','budget':10})
        schema = c.get('/api/custom/projects/schema', headers=auth)
        out.update({'bad':bad.status_code,'good':good.status_code,'dup':dup.status_code,'schema':schema.status_code,'fields':len(schema.json().get('fields',[]))})
    """)
    assert out['bad'] == 422
    assert out['good'] == 201
    assert out['dup'] == 409
    assert out['schema'] == 200
    assert out['fields'] == 3


def test_due_workflow_runner_executes_scheduled_action():
    out = run_app_script("""
    with TestClient(main.app) as c:
        c.post('/api/platform/workflow_rules', headers=auth, json={'name':'Scheduled lead task','module':'Leads','event':'create','status':'Active','criteria':[], 'actions':[{'type':'create_task','value':'Scheduled follow up'}], 'scheduled_for':'2000-01-01T00:00:00'})
        lead = c.post('/api/leads', headers=auth, json={'name':'Scheduled Lead','company':'Acme'})
        before = c.get('/api/activities?activity_type=Task&search=Scheduled%20follow%20up&limit=100', headers=auth).json()['total']
        run = c.post('/api/automation/workflows/run-due', headers=auth)
        after = c.get('/api/activities?activity_type=Task&search=Scheduled%20follow%20up&limit=100', headers=auth).json()['total']
        out.update({'lead':lead.status_code,'before':before,'run':run.status_code,'completed':run.json().get('completed'),'after':after})
    """)
    assert out['lead'] == 200
    assert out['before'] == 0
    assert out['run'] == 200
    assert out['completed'] == 1
    assert out['after'] == 1


def test_forecast_summary_is_calculated_from_deals():
    out = run_app_script("""
    with TestClient(main.app) as c:
        future = (date.today() + timedelta(days=10)).isoformat()
        c.post('/api/deals', headers=auth, json={'name':'Forecast Won','amount':1000,'stage':'Closed Won','probability':100,'expected_close_date':future,'status':'Won'})
        c.post('/api/deals', headers=auth, json={'name':'Forecast Commit','amount':2000,'stage':'Negotiation','probability':80,'expected_close_date':future,'status':'Open'})
        r = c.get(f'/api/forecast/summary?start={date.today().isoformat()}&end={(date.today()+timedelta(days=30)).isoformat()}&target=5000', headers=auth)
        data = r.json(); out.update({'code':r.status_code,'closed':data.get('closed_won'),'committed':data.get('committed'),'gap':data.get('gap')})
    """)
    assert out['code'] == 200
    assert out['closed'] >= 1000
    assert out['committed'] >= 2000
    assert out['gap'] <= 4000


def test_audit_filter_and_csv_export_are_admin_surfaces():
    out = run_app_script("""
    with TestClient(main.app) as c:
        c.post('/api/leads', headers=auth, json={'name':'Audit Lead','company':'Acme'})
        r = c.get('/api/audit?resource=leads&action=create&search=Created', headers=auth)
        e = c.get('/api/audit/export.csv?resource=leads', headers=auth)
        out.update({'code':r.status_code,'total':r.json().get('total'),'export':e.status_code,'type':e.headers.get('content-type',''),'has_header':'summary' in e.text.splitlines()[0]})
    """)
    assert out['code'] == 200 and out['total'] >= 1
    assert out['export'] == 200 and 'text/csv' in out['type'] and out['has_header']
