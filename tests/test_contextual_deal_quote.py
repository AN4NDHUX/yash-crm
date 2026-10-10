"""Contextual Account → Deal and Deal → Quote actions use real CRM persistence."""
from test_workflow_rule_builder import app_scenario


def test_account_to_deal_and_deal_to_quote_preserve_links_and_show_in_reports():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        signup=c.post('/api/auth/signup',json={
            'name':'Context Owner','organization_name':'Context Actions Workspace',
            'username':'context.owner','email':'context.owner@example.test',
            'password':'strong-password-123'})
        out['signup']=signup.status_code
        with main.SessionLocal() as db:
            user=db.scalar(main.select(main.User).where(main.User.email=='context.owner@example.test'))
            subscription=main._ensure_organization_subscription(db,user)
            plan=db.scalar(main.select(main.Plan).where(main.Plan.code=='professional'))
            subscription.plan_id=plan.id
            subscription.status='Active'
            db.commit()
        account=c.post('/api/accounts',json={'name':'Orbit Systems','phone':'+919811223300'}).json()
        contact=c.post('/api/contacts',json={'first_name':'Mira','last_name':'Roy',
            'email':'mira@example.test','account_id':account['id']}).json()
        deal=c.post('/api/deals',json={
            'name':'Orbit - Opportunity','account_id':account['id'],
            'contact_id':contact['id'],'amount':8700,'stage':'Qualification'}).json()
        out['deal_id']=deal['id']
        out['deal_account']=deal['account_id']
        out['deal_contact']=deal['contact_id']
        quote_response=c.post('/api/platform/quotes',json={
            'name':'Orbit - Quote','deal_id':deal['id'],
            'amount':8700,'status':'Draft','terms':'Net 30'})
        out['quote_status']=quote_response.status_code
        assert quote_response.status_code == 201, (
            quote_response.status_code, quote_response.text[:2000]
        )
        quote=quote_response.json()
        out['quote']=quote
        saved=c.get('/api/platform/quotes/'+str(quote['id'])).json()
        out['saved']=saved
        out['quote_listing']=c.get('/api/platform/quotes').json()['total']
        out['deal_related']=c.get('/api/deals/'+str(deal['id'])+'/related').json()
        out['account_deals']=[row for row in c.get('/api/deals').json()['items'] if row['account_id']==account['id']]
        out['account_count']=c.get('/api/accounts').json()['total']
        out['deal_count']=c.get('/api/deals').json()['total']
    """)
    assert out['signup']==201,out
    assert out['deal_account'] == out['saved']['account_id'],out
    assert out['deal_contact'] == out['saved']['contact_id'],out
    assert out['quote_status']==201,out
    assert out['saved']['deal_id']==out['deal_id'],out
    assert out['saved']['status']=='Draft',out
    assert out['saved']['terms']=='Net 30',out
    assert out['saved']['amount']==8700,out
    assert out['saved']['quote_number'].startswith('QT'),out
    assert out['quote_listing']==1 and out['account_count']==1 and out['deal_count']==1,out
    assert out['account_deals'][0]['id']==out['deal_id'],out
    assert any(item['id']==out['quote']['id'] and item['resource']=='quotes'
               for item in out['deal_related']['custom_records']),out


def test_quote_must_match_source_deal_account_and_contact():
    out=app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup',json={
            'name':'Quote Consistency','organization_name':'Quote Consistency Workspace',
            'username':'quote.consistency','email':'quote.consistency@example.test',
            'password':'strong-password-123'})
        with main.SessionLocal() as db:
            user=db.scalar(main.select(main.User).where(main.User.email=='quote.consistency@example.test'))
            subscription=main._ensure_organization_subscription(db,user)
            plan=db.scalar(main.select(main.Plan).where(main.Plan.code=='professional'))
            subscription.plan_id=plan.id
            subscription.status='Active'
            db.commit()
        a=c.post('/api/accounts',json={'name':'North'}).json()
        b=c.post('/api/accounts',json={'name':'South'}).json()
        x=c.post('/api/contacts',json={'first_name':'Max','last_name':'Lee','account_id':a['id']}).json()
        y=c.post('/api/contacts',json={'first_name':'Bea','last_name':'Lee','account_id':b['id']}).json()
        deal=c.post('/api/deals',json={'name':'North Deal','account_id':a['id'],'contact_id':x['id']}).json()
        out['bad_account']=c.post('/api/platform/quotes',json={
            'name':'Bad account','deal_id':deal['id'],'account_id':b['id']}).status_code
        out['bad_contact']=c.post('/api/platform/quotes',json={
            'name':'Bad contact','deal_id':deal['id'],'contact_id':y['id']}).status_code
        correct=c.post('/api/platform/quotes',json={
            'name':'Good quote','deal_id':deal['id'],'status':'Draft'})
        out['good_status']=correct.status_code
        out['good_account']=correct.json().get('account_id')
        out['good_contact']=correct.json().get('contact_id')
        out['expected_account']=a['id']
        out['expected_contact']=x['id']
        listing=c.get('/api/platform/quotes')
        assert listing.status_code == 200, (listing.status_code, listing.text[:2000])
        out['quote_count']=listing.json()['total']
    """)
    assert out['bad_account']==422,out
    assert out['bad_contact']==422,out
    assert out['good_status']==201,out
    assert out['good_account']==out['expected_account'],out
    assert out['good_contact']==out['expected_contact'],out
    assert out['quote_count']==1,out


def test_account_to_deal_keeps_account_and_prevents_identical_duplicates():
    out=app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup',json={
            'name':'Deal Builder','organization_name':'Deal Builder Workspace',
            'username':'deal.builder','email':'deal.builder@example.test',
            'password':'strong-password-123'})
        account=c.post('/api/accounts',json={'name':'Kite Labs'}).json()
        payload={'name':'Kite Labs - Opportunity','account_id':account['id'],
                 'stage':'Qualification','amount':1500,'status':'Open'}
        first=c.post('/api/deals',json=payload)
        out['first_status']=first.status_code
        out['first_account']=first.json().get('account_id')
        out['duplicate_status']=c.post('/api/deals',json=payload).status_code
        next_deal=c.post('/api/deals',json={**payload,'name':'Kite Labs - Expansion'})
        out['next_status']=next_deal.status_code
        out['account_count']=c.get('/api/accounts').json()['total']
        out['deal_count']=c.get('/api/deals').json()['total']
        out['account_id']=account['id']
    """)
    assert out['first_status']==200 and out['next_status']==200,out
    assert out['first_account']==out['account_id'],out
    assert out['duplicate_status']==409,out
    assert out['account_count']==1 and out['deal_count']==2,out
