from test_workflow_rule_builder import app_scenario


def test_bulk_delete_restore_and_workflow_soft_delete():
    out=app_scenario("""
    with TestClient(main.app) as c:
        c.post('/api/auth/signup',json={'name':'Recycle Owner','organization_name':'Recycle Org',
            'username':'recycle.owner','email':'recycle.owner@example.com','password':'strong-password-123'})
        first=c.post('/api/leads',json={'name':'Recycle A','company':'Example'})
        second=c.post('/api/leads',json={'name':'Recycle B','company':'Example'})
        ids=[first.json()['id'],second.json()['id']]
        deleted=c.post('/api/administration/bulk-delete',json={'resource':'leads','ids':ids})
        out['deleted']=deleted.status_code
        out['deleted_count']=deleted.json().get('deleted')
        out['bin']=c.get('/api/administration/recycle-bin').status_code
        restored=c.post('/api/administration/recycle-bin/bulk-restore',
            json={'resource':'leads','ids':ids})
        out['restored']=restored.status_code
        out['restored_count']=restored.json().get('restored')
        rule=c.post('/api/platform/workflow_rules',json={'name':'Delete Me',
            'module':'leads','event':'create','status':'Active',
            'actions':[{'type':'audit','value':'sample'}]})
        rid=rule.json()['id']
        out['rule_deleted']=c.delete('/api/platform/workflow_rules/'+str(rid)).status_code
        out['rule_absent']=rid not in [r['id'] for r in
            c.get('/api/platform/workflow_rules?limit=100').json()['items']]
    """)
    assert out['deleted']==200, out
    assert out['deleted_count']==2, out
    assert out['bin']==200, out
    assert out['restored']==200, out
    assert out['restored_count']==2, out
    assert out['rule_deleted']==200, out
    assert out['rule_absent'], out


def test_recycle_bin_rejects_invalid_bulk_and_cross_tenant_requests():
    out=app_scenario("""
    with TestClient(main.app) as c:
        c.post('/api/auth/signup',json={'name':'Org One','organization_name':'One Org',
            'username':'one.owner','email':'one.owner@example.com','password':'strong-password-123'})
        record=c.post('/api/leads',json={'name':'Secret','company':'Private'}).json()['id']
        c.post('/api/administration/bulk-delete',json={'resource':'leads','ids':[record]})
        c.post('/api/auth/logout')
        c.post('/api/auth/signup',json={'name':'Org Two','organization_name':'Two Org',
            'username':'two.owner','email':'two.owner@example.com','password':'strong-password-123'})
        out['cross_restore']=c.post('/api/administration/recycle-bin/bulk-restore',
            json={'resource':'leads','ids':[record]}).status_code
        out['cross_delete']=c.post('/api/administration/recycle-bin/permanent-delete',
            json={'resource':'leads','ids':[record]}).status_code
        out['invalid']=c.post('/api/administration/bulk-delete',
            json={'resource':'leads','ids':[True]}).status_code
    """)
    assert out['cross_restore']==404, out
    assert out['cross_delete']==404, out
    assert out['invalid']==422, out


def test_recycle_ui_has_selection_and_permanent_delete_controls():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    setup=(root/'static/js/features/setup.js').read_text()
    app=(root/'static/js/app.js').read_text()
    assert 'data-recycle-select-all' in setup
    assert 'data-recycle-permanent-selected' in setup
    assert 'data-recycle-restore-selected' in setup
    assert '/api/administration/recycle-bin/bulk-restore' in app


def test_recycle_restore_enforces_30_day_expiry():
    out=app_scenario("""
    from datetime import datetime, timedelta
    with TestClient(main.app) as c:
        c.post('/api/auth/signup',json={'name':'Retention Owner','organization_name':'Retention Org',
            'username':'retention.owner','email':'retention.owner@example.com','password':'strong-password-123'})
        lead=c.post('/api/leads',json={'name':'Expired Lead','company':'Example'})
        lid=lead.json()['id']
        c.delete('/api/leads/'+str(lid))
        with main.SessionLocal() as db:
            record=db.get(main.Lead,lid)
            record.updated_at=datetime.utcnow()-timedelta(days=31)
            db.commit()
        out['restore']=c.post('/api/administration/restore',
            json={'resource':'leads','record_id':lid}).status_code
        out['bulk_restore']=c.post('/api/administration/recycle-bin/bulk-restore',
            json={'resource':'leads','ids':[lid]}).status_code
    """)
    assert out['restore']==410, out
    assert out['bulk_restore']==410, out
