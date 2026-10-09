"""End-to-end scoped Deluge CRM task and outbound queue coverage."""
from test_workflow_rule_builder import app_scenario


def test_deluge_zoho_current_record_update_integrates_with_rule():
    result = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Deluge Owner','organization_name':'Deluge Task Org',
            'username':'deluge.owner','email':'deluge.owner@example.com',
            'password':'strong-password-123'
        })
        function = c.post('/api/platform/functions', json={
            'name':'Update Current Lead','runtime':'Deluge','entrypoint':'workflow',
            'source':{'code':'zoho.crm.updateRecord("Leads", $record.id, {"company":"Updated by Deluge"});'},
            'status':'Active'
        })
        out['function_status'] = function.status_code
        if function.status_code != 201:
            out['detail'] = function.text[:400]
        else:
            rule = c.post('/api/platform/workflow_rules', json={
                'name':'Run Deluge Task','module':'leads','event':'create',
                'actions':[{'type':'function','value':str(function.json()['id'])}],
                'status':'Active'
            })
            out['rule_status'] = rule.status_code
            lead = c.post('/api/leads', json={'name':'Deluge Test','company':'Original'})
            out['lead_status'] = lead.status_code
            if lead.status_code in (200,201):
                out['company'] = c.get('/api/leads/' + str(lead.json()['id'])).json().get('company')
    """)
    assert result['function_status'] == 201, result
    assert result['rule_status'] == 201, result
    assert result['lead_status'] in (200, 201), result
    assert result['company'] == 'Updated by Deluge', result


def test_deluge_invokeurl_creates_isolated_worker_job():
    result = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Deluge Queue','organization_name':'Deluge Queue Org',
            'username':'deluge.queue','email':'deluge.queue@example.com',
            'password':'strong-password-123'
        })
        function = c.post('/api/platform/functions', json={
            'name':'Notify External','runtime':'Deluge','entrypoint':'workflow',
            'source':{'code':'invokeurl("safe event");'},
            'status':'Active'
        })
        out['function_status'] = function.status_code
        if function.status_code == 201:
            rule = c.post('/api/platform/workflow_rules', json={
                'name':'Queue Deluge','module':'leads','event':'create',
                'actions':[{'type':'function','value':str(function.json()['id'])}],
                'status':'Active'
            })
            out['rule_status'] = rule.status_code
            lead = c.post('/api/leads', json={'name':'Queue Lead','company':'Company'})
            out['lead_status'] = lead.status_code
            with main.SessionLocal() as db:
                jobs = db.scalars(main.select(main.WorkflowExecution).where(
                    main.WorkflowExecution.rule_id == function.json()['id'],
                    main.WorkflowExecution.event == 'deluge_outbound',
                )).all()
                out['queued'] = len(jobs) == 1 and jobs[0].status == 'queued'
                out['payload'] = jobs[0].actions[0]['value'] if jobs else None
    """)
    assert result['function_status'] == 201, result
    assert result['rule_status'] == 201, result
    assert result['lead_status'] in (200, 201), result
    assert result['queued'] is True, result
    assert result['payload'] == 'safe event', result
