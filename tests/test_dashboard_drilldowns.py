from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_drilldowns_match_kpis_and_filter_closed_records():
    script = (
        "import base64, json\n"
        "from datetime import datetime, timedelta\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "auth = {'Authorization': 'Basic ' + base64.b64encode(b'admin:supersecretpass123').decode()}\n"
        "out = {}\n"
        + textwrap.dedent("""
        with TestClient(main.app) as c:
            def create(resource, payload):
                response = c.post('/api/' + resource, headers=auth, json=payload)
                assert response.status_code in (200, 201), (resource, response.text)
                return response.json()

            lead = create('leads', {'name': 'Dashboard Lead', 'status': 'New'})
            opened = create('deals', {'name': 'Dashboard Open', 'stage': 'Proposal', 'amount': 1234})
            closed = create('deals', {'name': 'Dashboard Closed', 'stage': 'Closed Lost', 'amount': 9999})
            due = create('activities', {'subject': 'Dashboard Due Task', 'activity_type': 'Task',
                'status': 'Open', 'due_at': (datetime.utcnow() + timedelta(days=2)).isoformat()})
            later = create('activities', {'subject': 'Dashboard Future Task', 'activity_type': 'Task',
                'status': 'Open', 'due_at': (datetime.utcnow() + timedelta(days=14)).isoformat()})
            completed = create('activities', {'subject': 'Dashboard Completed Task', 'activity_type': 'Task',
                'status': 'Completed', 'due_at': (datetime.utcnow() + timedelta(days=1)).isoformat()})

            dash = c.get('/api/dashboard', headers=auth).json()
            keys = ['total-leads', 'open-deals', 'pipeline-value', 'activities-due', 'ai-action-queue']
            reports = {}
            for key in keys:
                response = c.get('/api/dashboard/report/' + key, headers=auth)
                assert response.status_code == 200, (key, response.text)
                reports[key] = response.json()
            ids = lambda key: [row['id'] for row in reports[key]['items']]
            out['kpis_match'] = (
                reports['total-leads']['total'] == dash['metrics']['total_leads']
                and reports['open-deals']['total'] == dash['metrics']['open_deals']
                and reports['pipeline-value']['amount'] == dash['metrics']['pipeline_value']
                and reports['activities-due']['total'] == dash['metrics']['activities_due']
            )
            out['records_filtered'] = (
                lead['id'] in ids('total-leads')
                and opened['id'] in ids('open-deals') and closed['id'] not in ids('open-deals')
                and due['id'] in ids('activities-due')
                and later['id'] not in ids('activities-due')
                and completed['id'] not in ids('activities-due')
            )
            out['queue_match'] = reports['ai-action-queue']['total'] == sum(
                len(items) for items in dash['attention'].values()
            )
            paged = c.get('/api/dashboard/report/total-leads?limit=1', headers=auth).json()
            out['pagination'] = len(paged['items']) == 1 and paged['total'] == reports['total-leads']['total']
            out['invalid'] = c.get('/api/dashboard/report/invalid', headers=auth).status_code
            out['unauthorized'] = c.get('/api/dashboard/report/total-leads').status_code
        """)
        + "\nprint('RESULT' + json.dumps(out))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            'APP_ENV': 'development', 'DATABASE_URL': f'sqlite:///{tmp}/test.db',
            'ENABLE_AUTH': 'true', 'APP_USERNAME': 'admin',
            'APP_PASSWORD': 'supersecretpass123', 'ADMIN_EMAIL': 'admin@example.com',
            'SEED_DEMO_DATA': 'false', 'PYTHONPATH': str(ROOT)
        })
        proc = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-4000:]
    result = json.loads([line[6:] for line in proc.stdout.splitlines() if line.startswith('RESULT')][-1])
    assert result['kpis_match'] and result['records_filtered'], result
    assert result['queue_match'] and result['pagination'], result
    assert result['invalid'] == 404 and result['unauthorized'] in (401, 403), result


def test_dashboard_cards_link_to_five_report_routes():
    app_js = (ROOT / 'static/js/app.js').read_text(encoding='utf-8')
    for route in ('total-leads', 'open-deals', 'pipeline-value', 'activities-due', 'ai-action-queue'):
        assert f'data-go="/dashboard/report/{route}"' in app_js
    assert 'content.innerHTML = await dashboardReportView(parts[2])' in app_js
    assert 'aria-label="Open Total leads report"' in app_js
