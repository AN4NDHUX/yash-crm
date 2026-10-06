from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "admin"
PASSWORD = "supersecretpass123"


def run_app_script(body: str) -> dict:
    script = (
        "import base64, json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "token = base64.b64encode(b'admin:supersecretpass123').decode()\n"
        "auth = {'Authorization': 'Basic ' + token}\n"
        "out = {}\n"
        + textwrap.dedent(body)
        + "\nprint('RESULT' + json.dumps(out))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/test.db",
            "ENABLE_AUTH": "true",
            "APP_USERNAME": USERNAME,
            "APP_PASSWORD": PASSWORD,
            "PYTHONPATH": str(ROOT),
        })
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stderr[-3000:])
    line = [row for row in result.stdout.splitlines() if row.startswith("RESULT")][-1]
    return json.loads(line[len("RESULT"):])


def test_email_related_list_accepts_body_and_persists_it():
    out = run_app_script(
        """
        with TestClient(main.app) as c:
            lead = c.post('/api/leads', headers=auth, json={'name':'Email Test Lead','company':'Acme'}).json()
            email = c.post('/api/emails', headers=auth, json={
                'subject':'Welcome', 'body':'Hello from Yash CRM', 'status':'Draft',
                'related_type':'leads', 'related_id':lead['id']
            })
            related = c.get(f"/api/leads/{lead['id']}/related", headers=auth)
            out['email_code'] = email.status_code
            out['body'] = email.json().get('body')
            out['related_body'] = related.json()['emails'][0].get('body')
        """
    )
    assert out == {'email_code': 200, 'body': 'Hello from Yash CRM', 'related_body': 'Hello from Yash CRM'}


def test_workflow_executes_for_core_lead_create():
    out = run_app_script(
        """
        with TestClient(main.app) as c:
            rule = c.post('/api/platform/workflow_rules', headers=auth, json={
                'name':'Lead follow-up', 'module':'Leads', 'event':'create', 'status':'Active',
                'criteria':[], 'actions':[{'type':'create_task','value':'Call new lead'}]
            })
            lead = c.post('/api/leads', headers=auth, json={'name':'Workflow Lead','company':'Acme'})
            tasks = c.get('/api/activities?activity_type=Task&limit=100', headers=auth)
            out['rule'] = rule.status_code
            out['lead'] = lead.status_code
            out['tasks'] = [item['subject'] for item in tasks.json()['items']]
        """
    )
    assert out['rule'] == 201
    assert out['lead'] == 200
    assert 'Call new lead' in out['tasks']


def test_standard_module_csv_import_creates_leads():
    out = run_app_script(
        """
        with TestClient(main.app) as c:
            csv_data = b'name,company,email,status\\nImported Lead,Example Co,imported@example.com,New\\n'
            response = c.post('/api/import/leads', headers=auth, files={'file':('leads.csv', csv_data, 'text/csv')})
            leads = c.get('/api/leads?search=Imported%20Lead', headers=auth)
            out['code'] = response.status_code
            out['imported'] = response.json().get('imported')
            out['total'] = leads.json().get('total')
        """
    )
    assert out == {'code': 200, 'imported': 1, 'total': 1}
