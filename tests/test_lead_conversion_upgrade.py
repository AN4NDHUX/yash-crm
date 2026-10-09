from test_workflow_rule_builder import app_scenario


def test_optional_deal_conversion_and_idempotent_retry():
    out = app_scenario("""
    with TestClient(main.app) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Conversion Owner','organization_name':'Conversion Org',
            'username':'convert.owner','email':'convert.owner@example.com',
            'password':'strong-password-123'})
        assert signup.status_code in (200, 201), signup.text
        lead = c.post('/api/leads', json={
            'name':'Anita Rao','company':'Acme Example',
            'email':'anita.rao@example.com'}).json()
        url = '/api/leads/' + str(lead['id']) + '/convert'
        first = c.post(url, json={'create_deal':False})
        out['first_status'] = first.status_code
        out['first'] = first.json()
        second = c.post(url, json={'create_deal':False})
        out['retry_status'] = second.status_code
        out['second'] = second.json()
        out['leads_status'] = c.get('/api/leads/' + str(lead['id'])).json()['status']
    """)
    assert out['first_status'] == 200, out
    assert out['retry_status'] == 200, out
    assert out['first']['deal'] is None, out
    assert out['first']['contact']['id'] == out['second']['contact']['id'], out
    assert out['first']['account']['id'] == out['second']['account']['id'], out
    assert out['leads_status'] == 'Converted', out


def test_deal_conversion_requires_close_date_and_preserves_links():
    out = app_scenario("""
    with TestClient(main.app) as c:
        c.post('/api/auth/signup', json={
            'name':'Deal Conversion','organization_name':'Deal Conversion Org',
            'username':'deal.convert','email':'deal.convert@example.com',
            'password':'strong-password-123'})
        lead = c.post('/api/leads', json={
            'name':'David Lee','company':'Opportunity Example',
            'email':'david.lee@example.com'}).json()
        url = '/api/leads/' + str(lead['id']) + '/convert'
        missing = c.post(url, json={'create_deal':True,'deal_name':'Test Deal'})
        out['missing'] = missing.status_code
        converted = c.post(url, json={
            'create_deal':True,'deal_name':'Test Deal',
            'expected_close_date':'2026-12-31',
            'contact_role':'Decision Maker','stage':'Needs Analysis'})
        out['status'] = converted.status_code
        out['data'] = converted.json()
        retry = c.post(url, json={
            'create_deal':True,'expected_close_date':'2026-12-31'})
        out['retry'] = retry.json()
    """)
    assert out['missing'] == 422, out
    assert out['status'] == 200, out
    assert out['data']['deal']['name'] == 'Test Deal', out
    assert out['data']['deal']['contact_id'] == out['data']['contact']['id'], out
    assert out['data']['deal']['account_id'] == out['data']['account']['id'], out
    assert out['data']['deal']['id'] == out['retry']['deal']['id'], out


def test_custom_module_fields_and_related_rows_survive_conversion():
    out = app_scenario("""
    from app.models import PlatformRecord, MetadataModule, MetadataField, Note
    with TestClient(main.app) as c:
        c.post('/api/auth/signup', json={
            'name':'Custom Owner','organization_name':'Custom Conversion Org',
            'username':'custom.convert','email':'custom.convert@example.com',
            'password':'strong-password-123'})
        lead = c.post('/api/leads', json={
            'name':'Custom Lead','company':'Custom Company',
            'email':'custom.lead@example.com'}).json()
        with main.SessionLocal() as db:
            org = lead['organization_id']
            module = MetadataModule(api_name='custom_visits', label='Custom Visits',
                plural_label='Custom Visits', enabled=True, organization_id=org)
            db.add(module)
            db.flush()
            db.add(MetadataField(module_id=module.id, api_name='contact_id',
                label='Contact', field_type='lookup'))
            db.add(MetadataField(module_id=module.id, api_name='deal_id',
                label='Deal', field_type='lookup'))
            visit = PlatformRecord(resource='custom_visits', title='Important visit',
                organization_id=org, related_type='leads', related_id=lead['id'],
                data={'lead_id':lead['id'], 'customer_note':'Keep this custom text',
                      'nested':{'checklist':['one','two']}})
            note = Note(title='Lead note', content='Preserve', organization_id=org,
                related_type='leads', related_id=lead['id'])
            db.add_all([visit, note])
            db.commit()
            visit_id, note_id = visit.id, note.id
        converted = c.post('/api/leads/'+str(lead['id'])+'/convert', json={
            'create_deal':True,'deal_name':'Custom Deal',
            'expected_close_date':'2026-12-31'})
        out['status'] = converted.status_code
        if converted.status_code != 200:
            out['error'] = converted.text
        else:
            result = converted.json()
            with main.SessionLocal() as db:
                visit = db.get(PlatformRecord, visit_id)
                note = db.get(Note, note_id)
                out['original_lead_ref'] = visit.data.get('lead_id')
                out['nested'] = visit.data.get('nested')
                out['note_text'] = visit.data.get('customer_note')
                out['custom_contact'] = visit.data.get('contact_id')
                out['custom_deal'] = visit.data.get('deal_id')
                out['expected_contact'] = result['contact']['id']
                out['expected_deal'] = result['deal']['id']
                out['related_type'] = visit.related_type
                out['note_related_type'] = note.related_type
            related = c.get('/api/deals/' + str(result['deal']['id']) + '/related')
            out['related_http'] = related.status_code
            if related.status_code == 200:
                out['custom_titles'] = [row['title'] for row in related.json().get('custom_records', [])]

    """)
    assert out['status'] == 200, out
    assert out['original_lead_ref'] is not None, out
    assert out['nested'] == {'checklist':['one','two']}, out
    assert out['note_text'] == 'Keep this custom text', out
    assert out['custom_contact'] == out['expected_contact'], out
    assert out['custom_deal'] == out['expected_deal'], out
    assert out['related_type'] == 'deals', out
    assert out['note_related_type'] == 'deals', out
    assert out['related_http'] == 200, out
    assert 'Important visit' in out['custom_titles'], out
