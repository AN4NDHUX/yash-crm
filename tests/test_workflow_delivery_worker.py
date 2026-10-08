from __future__ import annotations

from test_workflow_rule_builder import app_scenario


def test_worker_claims_due_task_once():
    result = app_scenario("""
    from app.workflow_worker import process_due
    with TestClient(main.app, follow_redirects=False) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Due Worker', 'organization_name':'Due Worker Org',
            'username':'due.worker', 'email':'due.worker@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = signup.status_code
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Queue On Create','module':'leads','event':'create',
            'scheduled_for':'2020-01-01T00:00:00',
            'actions':[{'type':'create_task','value':'Scheduled Task'}],
            'status':'Active',
        })
        out['rule_status'] = rule.status_code
        lead = c.post('/api/leads', json={'name':'Due Lead','company':'Company'})
        out['lead_status'] = lead.status_code
        out['claimed'] = process_due()
        out['claimed_twice'] = process_due()
        executions = c.get('/api/automation/executions').json()['items']
        out['statuses'] = [row['status'] for row in executions if row['rule_id'] == rule.json()['id']]
        with main.SessionLocal() as db:
            out['tasks'] = db.scalar(main.select(main.func.count(main.Activity.id)).where(
                main.Activity.subject == 'Scheduled Task'))
    """)
    assert result["signup"] in (200, 201)
    assert result["rule_status"] == 201
    assert result["lead_status"] in (200, 201)
    assert result["claimed"] == 1
    assert result["claimed_twice"] == 0
    assert result["statuses"] == ["completed"]
    assert result["tasks"] == 1


def test_failed_webhook_delivery_is_retried_without_bypass():
    result = app_scenario("""
    from app.workflow_worker import process_due
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Webhook Worker','organization_name':'Webhook Worker Org',
            'username':'webhook.worker','email':'webhook.worker@example.com',
            'password':'strong-password-123'
        })
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Send Webhook','module':'leads','event':'create',
            'actions':[{'type':'webhook_queue','value':'safe payload'}], 'status':'Active'
        })
        c.post('/api/leads', json={'name':'Webhook Lead','company':'Company'})
        item = next(row for row in c.get('/api/automation/executions').json()['items']
                    if row['rule_id'] == rule.json()['id'])
        out['queued'] = item['status'] == 'queued'
        out['manual'] = c.post('/api/automation/executions/' + str(item['id']) + '/run').status_code
        out['claimed'] = process_due()
        after = next(row for row in c.get('/api/automation/executions').json()['items']
                     if row['id'] == item['id'])
        out['requeued'] = after['status'] == 'queued' and after['attempts'] == 1 and after['next_attempt_at'] is not None
    """)
    assert result == {"queued": True, "manual": 409, "claimed": 1, "requeued": True}


def test_failed_execution_can_be_requeued_by_org_admin():
    result = app_scenario("""
    from app.workflow_worker import process_due
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Retry Owner', 'organization_name':'Retry Org',
            'username':'retry.owner', 'email':'retry.owner@example.com',
            'password':'strong-password-123'
        })
        rule = c.post('/api/platform/workflow_rules', json={
            'name':'Broken Task','module':'leads','event':'create',
            'scheduled_for':'2020-01-01T00:00:00',
            'actions':[{'type':'field_update','field':'organization_id','value':999}],
            'status':'Active'
        })
        c.post('/api/leads', json={'name':'Retry Lead','company':'Company'})
        execution = next(row for row in c.get('/api/automation/executions').json()['items']
                         if row['rule_id'] == rule.json()['id'])
        with main.SessionLocal() as db:
            target = db.get(main.WorkflowExecution, execution['id'])
            target.status = 'failed'
            target.attempts = 5
            db.commit()
        response = c.post('/api/automation/executions/' + str(execution['id']) + '/retry')
        out['response'] = response.status_code
        updated = next(row for row in c.get('/api/automation/executions').json()['items']
                       if row['id'] == execution['id'])
        out['queued'] = updated['status'] == 'queued' and updated['attempts'] == 0
    """)
    assert result == {"response": 200, "queued": True}


def test_webhook_url_requires_server_side_https_configuration():
    result = app_scenario("""
    from app.workflow_worker import _send_external
    from types import SimpleNamespace
    action = {'type':'webhook_queue','url':'http://127.0.0.1/admin','value':'payload'}
    fake = SimpleNamespace(id=1, resource='leads', record_id=1, organization_id=1,
                           idempotency_key='key')
    try:
        _send_external(action, fake)
        out['rejected'] = False
    except ValueError:
        out['rejected'] = True
    """)
    assert result["rejected"] is True


def test_smtp_delivery_uses_tls_and_allowlisted_recipient():
    result = app_scenario("""
    import os
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.workflow_worker import _send_external
    os.environ.update({
        'WORKFLOW_EMAIL_RECIPIENTS':'allowed@example.com',
        'WORKFLOW_SMTP_HOST':'smtp.example.com',
        'WORKFLOW_SMTP_USER':'service',
        'WORKFLOW_SMTP_PASSWORD':'test-only',
        'WORKFLOW_EMAIL_FROM':'crm@example.com',
    })
    calls = []
    class FakeSMTP:
        def __init__(self,*args,**kwargs): calls.append('connect')
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def starttls(self,**kwargs): calls.append('starttls')
        def login(self,*args): calls.append('login')
        def send_message(self,message):
            calls.append('send')
            out['recipient'] = message['To']
            out['subject'] = message['Subject']
    with patch('app.workflow_worker.smtplib.SMTP', FakeSMTP):
        _send_external({'type':'email','to':'allowed@example.com',
            'subject':'Welcome','body':'Hello'},
            SimpleNamespace(id=9,resource='leads',record_id=2,
            organization_id=1,idempotency_key='test-9'))
    out['calls'] = calls
    """)
    assert result['calls'] == ['connect','starttls','login','send']
    assert result['recipient'] == 'allowed@example.com'
    assert result['subject'] == 'Welcome'


def test_webhook_delivery_is_signed_and_has_idempotency_header():
    result = app_scenario("""
    import os, hmac, hashlib
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.workflow_worker import _send_external
    os.environ['WORKFLOW_WEBHOOK_URL'] = 'https://hooks.example.com/crm'
    os.environ['WORKFLOW_WEBHOOK_SECRET'] = 'a' * 40
    class FakeResponse:
        status = 202
        def __enter__(self): return self
        def __exit__(self,*args): pass
    class FakeOpener:
        def open(self,request,timeout):
            raw = request.data
            out['signature_valid'] = request.get_header('X-crm-signature') == (
                'sha256=' + hmac.new(('a'*40).encode(),raw,hashlib.sha256).hexdigest())
            out['idempotency'] = request.get_header('X-crm-idempotency-key')
            out['url'] = request.full_url
            return FakeResponse()
    with patch('app.workflow_worker.build_opener', return_value=FakeOpener()):
        _send_external({'type':'webhook_queue','value':'test'},
            SimpleNamespace(id=9, resource='leads', record_id=2,
            organization_id=1,idempotency_key='test-9'))
    """)
    assert result['signature_valid'] is True
    assert result['idempotency'] == 'test-9'
    assert result['url'] == 'https://hooks.example.com/crm'
