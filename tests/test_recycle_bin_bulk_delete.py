from __future__ import annotations

from test_workflow_rule_builder import app_scenario


def test_bulk_delete_and_restore_leads_and_reports():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup',json={
            'name':'Recycle Administrator','organization_name':'Recycle Workspace',
            'username':'recycle.admin','email':'recycle.admin@example.com',
            'password':'strong-password-123'
        })
        lead_ids=[]
        for n in ('First Lead','Second Lead'):
            created=c.post('/api/leads',json={'name':n,'company':'Example'})
            lead_ids.append(created.json()['id'])
        response=c.post('/api/administration/bulk-delete',json={'resource':'leads','ids':lead_ids})
        out['bulk_status']=response.status_code
        out['bulk_deleted']=response.json().get('deleted')
        out['visible_after']=c.get('/api/leads?limit=100').json()['total']
        bin_response=c.get('/api/administration/recycle-bin')
        out['in_bin']=all(any(item['resource']=='leads' and item['id']==i for item in bin_response.json()['items']) for i in lead_ids)
        restored=c.post('/api/administration/restore',json={'resource':'leads','record_id':lead_ids[0]})
        out['restored']=restored.status_code
        out['visible_restored']=c.get('/api/leads?limit=100').json()['total']
        report=c.post('/api/platform/reports',json={'name':'Recycle Report','module':'leads','status':'Active'})
        out['report_created']=report.status_code
        if report.status_code==201:
            rid=report.json()['id']
            out['report_deleted']=c.post('/api/administration/bulk-delete',json={'resource':'reports','ids':[rid]}).status_code
            out['report_restored']=c.post('/api/administration/restore',json={'resource':'reports','record_id':rid}).status_code
    """)
    assert out['bulk_status']==200
    assert out['bulk_deleted']==2
    assert out['in_bin']
    assert out['visible_restored']==out['visible_after']+1
    assert out['restored']==200
    assert out['report_created']==201
    assert out['report_deleted']==200
    assert out['report_restored']==200


def test_bulk_delete_rejects_invalid_or_mixed_record_ids():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup',json={
            'name':'Bulk Administrator','organization_name':'Bulk Workspace',
            'username':'bulk.admin','email':'bulk.admin@example.com',
            'password':'strong-password-123'
        })
        lead=c.post('/api/leads',json={'name':'Preserved Lead','company':'Example'}).json()
        out['invalid']=c.post('/api/administration/bulk-delete',json={'resource':'leads','ids':['1']}).status_code
        out['missing']=c.post('/api/administration/bulk-delete',json={'resource':'leads','ids':[lead['id'],9999999]}).status_code
        out['still_visible']=any(r['id']==lead['id'] for r in c.get('/api/leads?limit=100').json()['items'])
    """)
    assert out=={'invalid':422,'missing':404,'still_visible':True}


def test_workflow_rule_delete_and_restore_from_recycle_bin():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup',json={
            'name':'Workflow Delete Admin','organization_name':'Workflow Delete Org',
            'username':'workflow.delete.admin','email':'workflow.delete@example.com',
            'password':'strong-password-123'
        })
        created=c.post('/api/platform/workflow_rules',json={
            'name':'Delete Me','module':'leads','event':'create','status':'Active',
            'actions':[{'type':'audit','value':'test'}]
        })
        out['created']=created.status_code
        rule_id=created.json()['id']
        out['deleted']=c.delete('/api/platform/workflow_rules/'+str(rule_id)).status_code
        out['hidden']=all(x['id']!=rule_id for x in c.get('/api/platform/workflow_rules').json()['items'])
        out['recycled']=any(x['id']==rule_id and x['resource']=='workflow_rules' for x in c.get('/api/administration/recycle-bin').json()['items'])
        out['restored']=c.post('/api/administration/restore',json={'resource':'workflow_rules','record_id':rule_id}).status_code
    """)
    assert out=={'created':201,'deleted':200,'hidden':True,'recycled':True,'restored':200}


def test_recycle_bin_purges_records_older_than_thirty_days():
    out = app_scenario("""
    from datetime import datetime, timedelta
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup',json={
            'name':'Retention Admin','organization_name':'Retention Workspace',
            'username':'retention.admin','email':'retention.admin@example.com',
            'password':'strong-password-123'
        })
        lead=c.post('/api/leads',json={'name':'Old Deleted Lead','company':'Example'}).json()
        lid=lead['id']
        c.delete('/api/leads/'+str(lid))
        with main.SessionLocal() as db:
            row=db.get(main.Lead,lid)
            row.updated_at=datetime.utcnow()-timedelta(days=31)
            db.commit()
        purge=c.post('/api/administration/recycle-bin/purge-expired')
        out['purge_status']=purge.status_code
        out['purged']=purge.json().get('purged',0)
        out['absent']=not any(item['resource']=='leads' and item['id']==lid for item in
                           c.get('/api/administration/recycle-bin').json()['items'])
    """)
    assert out['purge_status']==200
    assert out['purged']>=1
    assert out['absent']
