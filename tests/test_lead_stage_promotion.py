"""Contacted and Converted must promote a single Lead without duplicate CRM records."""
from test_workflow_rule_builder import app_scenario


def test_contacted_creates_linked_parties_once_and_converted_creates_single_deal():
    out = app_scenario("""
    with TestClient(main.app) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Lifecycle Owner','organization_name':'Lifecycle Workspace',
            'username':'lifecycle.owner','email':'lifecycle.owner@example.test',
            'password':'strong-password-123'})
        assert signup.status_code == 201, signup.text
        created = c.post('/api/leads', json={
            'name':'Anna Kane', 'company':'Bright Brands',
            'email':'anna.kane@example.test', 'phone':'+919900110022',
            'notes':'Preserve this lead note'}).json()
        lead_id = created['id']
        out['initial_accounts'] = c.get('/api/accounts').json()['total']
        out['initial_contacts'] = c.get('/api/contacts').json()['total']
        contacted = c.patch(f'/api/leads/{lead_id}', json={'status':'Contacted'})
        out['contacted_http'] = contacted.status_code
        out['contacted'] = contacted.json()
        linked = contacted.json()
        repeated = c.patch(f'/api/leads/{lead_id}', json={'status':'Contacted'})
        out['repeated_http'] = repeated.status_code
        out['same_links'] = repeated.json().get('converted_account_id') == linked.get('converted_account_id') and repeated.json().get('converted_contact_id') == linked.get('converted_contact_id')
        out['parties_after_repeat'] = (c.get('/api/accounts').json()['total'], c.get('/api/contacts').json()['total'])
        out['deal_count_before_conversion'] = c.get('/api/deals').json()['total']
        qualified = c.patch(f'/api/leads/{lead_id}', json={'status':'Qualified'})
        out['qualified_http'] = qualified.status_code
        converted = c.patch(f'/api/leads/{lead_id}', json={'status':'Converted'})
        out['converted_http'] = converted.status_code
        out['converted'] = converted.json()
        out['accounts'] = c.get('/api/accounts').json()
        out['contacts'] = c.get('/api/contacts').json()
        out['deals'] = c.get('/api/deals').json()
        out['active_leads'] = c.get('/api/leads').json()['total']
        out['historical_lead'] = c.get(f'/api/leads/{lead_id}').json()
        out['repeat_converted'] = c.patch(f'/api/leads/{lead_id}',json={'status':'Converted'}).status_code
        out['reverse'] = c.patch(f'/api/leads/{lead_id}',json={'status':'New'}).status_code
        out['final_deals'] = c.get('/api/deals').json()['total']
        out['related'] = c.get(f'/api/deals/{converted.json().get("converted_deal_id")}').json()
    """)
    assert out['initial_accounts'] == 0 and out['initial_contacts'] == 0, out
    assert out['contacted_http'] == 200 and out['repeated_http'] == 200, out
    assert out['same_links'] and out['parties_after_repeat'] == [1, 1], out
    assert out['deal_count_before_conversion'] == 0, out
    assert out['qualified_http'] == 200 and out['converted_http'] == 200, out
    assert out['accounts']['total'] == 1 and out['contacts']['total'] == 1, out
    assert out['deals']['total'] == 1 and out['final_deals'] == 1, out
    assert out['active_leads'] == 0 and out['historical_lead']['status'] == 'Converted', out
    assert out['repeat_converted'] == 409 and out['reverse'] == 409, out
    assert out['related']['origin_lead_id'] == out['historical_lead']['id'], out
    assert out['related']['contact_id'] == out['converted']['converted_contact_id'], out
    assert out['related']['account_id'] == out['converted']['converted_account_id'], out


def test_blueprint_stage_transition_creates_parties_and_deal():
    out = app_scenario("""
    with TestClient(main.app) as c:
        c.post('/api/auth/signup', json={
            'name':'Blueprint Promotions','organization_name':'Blueprint Promotions Workspace',
            'username':'blueprint.promotions','email':'bp.promotions@example.test',
            'password':'strong-password-123'})
        lead = c.post('/api/leads',json={'name':'John Peters','company':'Arbor Labs','email':'john.peters@example.test'}).json()
        with main.SessionLocal() as db:
            db.add(main.Blueprint(organization_id=lead['organization_id'],
                name='Contact-to-Deal Process',module='Leads',active=True,archived=False,
                transitions=[{'from':'New','to':'Contacted','id':'contact','label':'Contact'},
                             {'from':'Contacted','to':'Converted','id':'convert','label':'Convert'}]))
            db.commit()
        first = c.post(f"/api/blueprint-records/leads/{lead['id']}/transition",json={'transition_id':'contact'})
        out['first_http'] = first.status_code
        out['first_status'] = first.json().get('status')
        out['first_account'] = first.json().get('converted_account_id')
        out['first_contact'] = first.json().get('converted_contact_id')
        second = c.post(f"/api/blueprint-records/leads/{lead['id']}/transition",json={'transition_id':'convert'})
        out['second_http'] = second.status_code
        out['second_status'] = second.json().get('status')
        out['second_deal'] = second.json().get('converted_deal_id')
        out['counts'] = [c.get(f'/api/{resource}').json()['total'] for resource in ('leads','accounts','contacts','deals')]
    """)
    assert out['first_http'] == 200 and out['first_status'] == "Contacted", out
    assert out['first_account'] and out['first_contact'], out
    assert out['second_http'] == 200 and out['second_status'] == "Converted", out
    assert out['second_deal'], out
    assert out['counts'] == [0, 1, 1, 1], out


def test_core_duplicate_prevention_and_cross_org_isolation():
    out = app_scenario("""
    with TestClient(main.app) as c:
        c.post('/api/auth/signup', json={
            'name':'Unique Owner','organization_name':'Dedup Workspace',
            'username':'dedup.owner','email':'dedup.owner@example.test',
            'password':'strong-password-123'})
        lead=c.post('/api/leads',json={'name':'Sana Roy','email':'sana.roy@example.test','phone':'100200300'})
        out['lead_status']=lead.status_code
        out['dup_lead']=c.post('/api/leads',json={'name':'Other Lead','email':'SANA.ROY@example.test'}).status_code
        account=c.post('/api/accounts',json={'name':'Tangent LLC'})
        out['account_status']=account.status_code
        out['dup_account']=c.post('/api/accounts',json={'name':' tangent llc '}).status_code
        contact=c.post('/api/contacts',json={'first_name':'Sana','last_name':'Roy',
                        'email':'sana.roy@example.test','phone':'100200300'})
        out['contact_status']=contact.status_code
        out['dup_contact']=c.post('/api/contacts',json={'first_name':'Other','last_name':'Person',
                        'phone':'100200300'}).status_code
        deal_payload={'name':'Sana Opportunity','account_id':account.json()['id'],'contact_id':contact.json()['id']}
        deal=c.post('/api/deals',json=deal_payload)
        out['deal_status']=deal.status_code
        out['dup_deal']=c.post('/api/deals',json=deal_payload).status_code
        out['other_deal']=c.post('/api/deals',json={'name':'Sana Opportunity'}).status_code
        out['counts']=[c.get(f'/api/{resource}').json()['total'] for resource in ('leads','accounts','contacts','deals')]
    with TestClient(main.app) as other:
        other.post('/api/auth/signup',json={
            'name':'Separate Org','organization_name':'Other Workspace',
            'username':'dedup.other','email':'dedup.other@example.test',
            'password':'strong-password-123'})
        out['other_org_same_email']=other.post('/api/leads',json={
            'name':'Sana Roy','email':'sana.roy@example.test'}).status_code
    """)
    assert out['lead_status'] == 201, out
    assert out['dup_lead'] == 409, out
    assert out['account_status'] == 201 and out['dup_account'] == 409, out
    assert out['contact_status'] == 201 and out['dup_contact'] == 409, out
    assert out['deal_status'] == 201 and out['dup_deal'] == 409, out
    assert out['other_deal'] == 201 and out['counts'] == [1,1,1,2], out
    assert out['other_org_same_email'] == 201, out
