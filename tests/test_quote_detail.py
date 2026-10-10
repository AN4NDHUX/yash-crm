"""Quote detail API and Zoho-inspired UI contracts exercised with demo organizations."""
from pathlib import Path

from test_workflow_rule_builder import app_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_quote_detail_related_records_and_organization_isolation():
    out = app_scenario("""
    with TestClient(main.app) as client:
        signup = client.post('/api/auth/signup', json={
            'name':'Quote Detail Owner','organization_name':'Quote Detail Demo',
            'username':'quote.detail.owner','email':'quote.detail.owner@example.test',
            'password':'strong-password-123'})
        assert signup.status_code in (200,201), signup.text
        with main.SessionLocal() as db:
            user = db.scalar(main.select(main.User).where(main.User.email == 'quote.detail.owner@example.test'))
            subscription = main._ensure_organization_subscription(db, user)
            plan = db.scalar(main.select(main.Plan).where(main.Plan.code == 'professional'))
            subscription.plan_id = plan.id
            subscription.status = 'Active'
            db.commit()
        acc = client.post('/api/accounts', json={'name':'Demo Buyer Account'}).json()
        deal = client.post('/api/deals', json={'name':'Demo Buyer Deal',
            'account_id':acc['id'],'amount':17500}).json()
        created = client.post('/api/platform/quotes', json={
            'name':'Demo Equipment Quotation', 'deal_id':deal['id'],
            'valid_until':'2026-12-30','status':'Draft','terms':'Net 30 days'})
        out['quote_code'] = created.status_code
        quote = created.json()
        out['quote_id'] = quote['id']
        out['quote_number'] = quote.get('quote_number')
        note = client.post('/api/notes', json={'title':'Quote review',
            'content':'Send for approval','related_type':'quotes','related_id':quote['id']})
        out['note_code'] = note.status_code
        order = client.post('/api/platform/sales_orders', json={
            'name':'Demo Sales Order','quote_id':quote['id'],'status':'Draft'})
        out['order_code'] = order.status_code
        out['order'] = order.json() if order.status_code == 201 else {}
        invoice = client.post('/api/platform/invoices', json={
            'name':'Demo Invoice', 'sales_order_id':out['order'].get('id'),
            'status':'Draft'})
        out['invoice_code'] = invoice.status_code
        detail = client.get('/api/platform/quotes/'+str(quote['id']))
        related = client.get('/api/platform/quotes/'+str(quote['id'])+'/related')
        out['detail_code'] = detail.status_code
        out['related_code'] = related.status_code
        out['detail'] = detail.json()
        out['related'] = related.json()
    with TestClient(main.app) as stranger:
        signup = stranger.post('/api/auth/signup',json={
            'name':'Other Quote User', 'organization_name':'Other Quote Workspace',
            'username':'other.quote.owner','email':'other.quote.owner@example.test',
            'password':'strong-password-123'})
        assert signup.status_code in (200,201), signup.text
        out['other_detail'] = stranger.get('/api/platform/quotes/'+str(out['quote_id'])).status_code
        out['other_related'] = stranger.get('/api/platform/quotes/'+str(out['quote_id'])+'/related').status_code
    """)
    assert out['quote_code'] == 201 and out['quote_number'].startswith(('QT','QUO-')), out
    assert out['note_code'] in (200,201), out
    assert out['order_code'] == 201 and out['invoice_code'] == 201, out
    assert out['detail_code'] == 200 and out['related_code'] == 200, out
    assert out['detail']['name'] == 'Demo Equipment Quotation', out
    related = out['related']
    assert related['accounts'][0]['id'] == out['detail']['account_id'], out
    assert related['deals'][0]['id'] == out['detail']['deal_id'], out
    assert any(n['title'] == 'Quote review' for n in related['notes']), out
    assert len(related['sales_orders']) == 1 and len(related['invoices']) == 1, out
    assert related['sales_orders'][0]['quote_id'] == out['quote_id'], out
    assert related['invoices'][0]['sales_order_id'] == out['order']['id'], out
    assert any(event['action'] == 'create' for event in related['timeline']), out
    assert out['other_detail'] in (403,404) and out['other_related'] in (403,404), out


def test_quote_details_route_actions_and_responsive_styles_wired():
    js = (ROOT / 'static/js/app.js').read_text(encoding='utf-8')
    detail = (ROOT / 'static/js/features/quote-details.js').read_text(encoding='utf-8')
    table = (ROOT / 'static/js/features/platform-table.js').read_text(encoding='utf-8')
    css = (ROOT / 'static/css/modules.css').read_text(encoding='utf-8')
    assert 'if (resource === "quotes" && parts[1])' in js
    assert 'href="/quotes/${Number(row.id)}"' in table
    assert 'createQuoteDetails' in js
    assert 'data-quote-tab="overview"' in detail and 'data-quote-tab="timeline"' in detail
    assert 'data-quote-convert="sales_orders"' in detail
    assert 'data-quote-convert="invoices"' in detail
    assert 'data-quote-add-note' in detail and 'data-quote-edit' in detail
    assert 'data-quote-archive' in detail and 'data-quote-related-open' in detail
    assert '/api/platform/quotes/${id}/related' in detail
    assert '@media(max-width:820px)' in css
