"""End-to-end Deluge CRM task and HTTP worker queue permission tests."""
from test_workflow_rule_builder import app_scenario


def test_crm_task_reads_and_updates_current_workspace_record():
    result = app_scenario("""
    from app.database import TENANT_ACTOR_ID, TENANT_ORGANIZATION_ID
    from app.deluge_crm_tasks import run_crm_task
    from app.models import User, OrganizationMember
    with TestClient(main.app, follow_redirects=False) as client:
        response = client.post('/api/auth/signup', json={
            'name':'Deluge API Tester', 'organization_name':'CRM Task Org',
            'username':'deluge.task.user', 'email':'deluge.task@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = response.status_code
        lead = client.post('/api/leads', json={'name':'Deluge Lead', 'company':'Example Org'})
        out['created'] = lead.status_code
        lead_id = lead.json()['id']
        with main.SessionLocal() as db:
            user = db.scalar(main.select(User).where(User.username == 'deluge.task.user'))
            membership = db.scalar(main.select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.status == 'Active',
            ))
            org_token = TENANT_ORGANIZATION_ID.set(membership.organization_id)
            actor_token = TENANT_ACTOR_ID.set(user.id)
            try:
                found = run_crm_task(db, 'getRecordById', ['Leads', lead_id], source_resource='leads')
                out['company'] = found['company']
                out['search'] = len(run_crm_task(db, 'searchRecords',
                    ['Leads', '(company:equals:Example Org)'], source_resource='leads'))
                out['list'] = len(run_crm_task(db, 'getRecords',
                    ['Leads', None, 1, 20], source_resource='leads'))
                update = run_crm_task(db, 'updateRecord',
                    ['Leads', lead_id, {'company':'Updated Org'}], source_resource='leads')
                out['update'] = update['status']
                db.commit()
                try:
                    run_crm_task(db, 'getRecordById', ['Users', user.id], source_resource='leads')
                    out['users_blocked'] = False
                except ValueError:
                    out['users_blocked'] = True
                org2 = TENANT_ORGANIZATION_ID.set(membership.organization_id + 999)
                try:
                    run_crm_task(db, 'getRecordById', ['Leads', lead_id], source_resource='leads')
                    out['cross_org_blocked'] = False
                except ValueError:
                    out['cross_org_blocked'] = True
                finally:
                    TENANT_ORGANIZATION_ID.reset(org2)
            finally:
                TENANT_ACTOR_ID.reset(actor_token)
                TENANT_ORGANIZATION_ID.reset(org_token)
        out['updated_company'] = client.get('/api/leads/' + str(lead_id)).json()['company']
    """)
    assert result["signup"] in (200, 201), result
    assert result["created"] in (200, 201), result
    assert result["company"] == "Example Org", result
    assert result["search"] >= 1, result
    assert result["list"] >= 1, result
    assert result["update"] == "success", result
    assert result["updated_company"] == "Updated Org", result
    assert result["users_blocked"] is True, result
    assert result["cross_org_blocked"] is True, result


def test_deluge_crm_get_record_by_id_executes_in_function():
    result = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Deluge Lookup', 'organization_name':'Lookup Org',
            'username':'deluge.lookup', 'email':'deluge.lookup@example.com',
            'password':'strong-password-123'
        })
        source = ('fetched = zoho.crm.v8.getRecordById("Leads", $record.id);\\n'
                  'if (fetched.get("company") == "Example") {\\n'
                  'crm.addTag("Lookup Confirmed");\\n'
                  '}\\n')
        fn = c.post('/api/platform/functions', json={
            'name':'Lookup Current Lead','runtime':'Deluge',
            'entrypoint':'workflow','source':{'code':source},'status':'Active'
        })
        out['fn'] = fn.status_code
        out['detail'] = fn.text[:300]
        if fn.status_code == 201:
            rule = c.post('/api/platform/workflow_rules', json={
                'name':'Lookup On Create','module':'leads','event':'create',
                'actions':[{'type':'function','value':str(fn.json()['id'])}],
                'status':'Active'
            })
            out['rule'] = rule.status_code
            lead = c.post('/api/leads', json={'name':'Lookup Lead','company':'Example'})
            out['lead'] = lead.status_code
            if lead.status_code in (200, 201):
                data = c.get('/api/leads/' + str(lead.json()['id'])).json()
                out['tags'] = data.get('tags')
    """)
    assert result["fn"] == 201, result
    assert result["rule"] == 201, result
    assert result["lead"] in (200, 201), result
    assert "Lookup Confirmed" in (result.get("tags") or []), result


def test_deluge_bracket_http_creates_durable_queue():
    result = app_scenario("""
    from app.models import WorkflowExecution
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Deluge Outbound', 'organization_name':'Outbound Org',
            'username':'deluge.outbound', 'email':'deluge.outbound@example.com',
            'password':'strong-password-123'
        })
        source = ('response = invokeurl\\n[\\n'
                  'url: "https://api.partner.example.com/hooks"\\n'
                  'type: POST\\n'
                  'connection: "partner"\\n'
                  'body: {"source":"crm"}\\n'
                  '];\\n')
        fn = c.post('/api/platform/functions', json={
            'name':'Partner Http','runtime':'Deluge','entrypoint':'workflow',
            'source':{'code':source},'status':'Active'
        })
        out['fn'] = fn.status_code
        out['detail'] = fn.text[:300]
        if fn.status_code == 201:
            rule = c.post('/api/platform/workflow_rules', json={
                'name':'Notify Partner','module':'leads','event':'create',
                'actions':[{'type':'function','value':str(fn.json()['id'])}],
                'status':'Active'
            })
            out['rule'] = rule.status_code
            lead = c.post('/api/leads', json={'name':'Outbound Lead','company':'Example'})
            out['lead'] = lead.status_code
            with main.SessionLocal() as db:
                jobs = db.scalars(main.select(WorkflowExecution).where(
                    WorkflowExecution.event == "deluge_http",
                )).all()
                out['queued'] = len(jobs) == 1 and jobs[0].status == 'queued'
                out['method'] = jobs[0].actions[0]['method'] if jobs else None
                out['connection'] = jobs[0].actions[0]['connection'] if jobs else None
    """)
    assert result["fn"] == 201, result
    assert result["rule"] == 201, result
    assert result["lead"] in (200, 201), result
    assert result["queued"] is True, result
    assert result["method"] == "POST", result
    assert result["connection"] == "partner", result
