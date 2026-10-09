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
