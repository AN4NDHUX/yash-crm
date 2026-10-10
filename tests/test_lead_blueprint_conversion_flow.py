"""Demo tenant regression: Account + Contact at Contacted; Deal only at Convert."""
from pathlib import Path
from test_workflow_rule_builder import app_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_demo_account_advances_blueprint_and_converts_only_on_explicit_transition():
    out = app_scenario("""
    with TestClient(main.app) as c:
        signup = c.post('/api/auth/signup', json={
            'name': 'Demo Blueprint Owner',
            'organization_name': 'Demo Blueprint Test Workspace',
            'username': 'demo.blueprint.owner',
            'email': 'demo.blueprint@example.test',
            'password': 'strong-password-123',
        })
        assert signup.status_code in (200, 201), signup.text
        lead_response = c.post('/api/leads', json={
            'name': 'Demo Buyer', 'company': 'Demo Account Limited',
            'email': 'demo.buyer@example.test', 'phone': '+919876540321',
        })
        assert lead_response.status_code in (200, 201), lead_response.text
        lead = lead_response.json()
        with main.SessionLocal() as db:
            db.add(main.Blueprint(
                organization_id=lead['organization_id'],
                name='Demo four-stage Blueprint', module='Leads',
                field_name='status', layout_name='Default',
                active=True, draft=False, archived=False,
                stages=[{'label': stage} for stage in ('New', 'Contacted', 'Qualified', 'Converted')],
                transitions=[
                    {'id': 'contact', 'label': 'Contact', 'from': 'New', 'to': 'Contacted'},
                    {'id': 'qualify', 'label': 'Qualify', 'from': 'Contacted', 'to': 'Qualified'},
                    {'id': 'convert', 'label': 'Convert', 'from': 'Qualified', 'to': 'Converted'},
                ],
            ))
            db.commit()
        url = f"/api/blueprint-records/leads/{lead['id']}/transition"
        def counts():
            return [c.get('/api/' + resource).json()['total']
                    for resource in ('leads', 'accounts', 'contacts', 'deals')]

        out['initial_counts'] = counts()
        contacted = c.post(url, json={'transition_id': 'contact'})
        out['contacted_code'] = contacted.status_code
        out['contacted'] = contacted.json()
        out['after_contact'] = counts()
        contacted_timeline = c.get(f"/api/leads/{lead['id']}/timeline").json()
        out['after_contact_stage'] = contacted_timeline['current_stage']
        out['after_contact_edges'] = [t['label'] for t in contacted_timeline['transition_details']]

        qualified = c.post(url, json={'transition_id': 'qualify'})
        out['qualified_code'] = qualified.status_code
        out['qualified'] = qualified.json()
        out['after_qualify'] = counts()
        out['after_qualify_edges'] = [t['label'] for t in
            c.get(f"/api/leads/{lead['id']}/timeline").json()['transition_details']]

        bypass_patch = c.patch(f"/api/leads/{lead['id']}", json={'status': 'Converted'})
        out['bypass_patch'] = bypass_patch.status_code
        bypass_api = c.post(f"/api/leads/{lead['id']}/convert",
                            json={'create_deal': True, 'expected_close_date': '2026-12-31'})
        out['bypass_api'] = bypass_api.status_code
        out['before_convert'] = counts()

        converted = c.post(url, json={'transition_id': 'convert'})
        out['converted_code'] = converted.status_code
        out['converted'] = converted.json()
        out['after_convert'] = counts()
        out['terminal_edges'] = c.get(f"/api/leads/{lead['id']}/timeline").json()['transition_details']
        deal_id = converted.json().get('converted_deal_id')
        out['deal'] = c.get(f'/api/deals/{deal_id}').json() if deal_id else {}
        out['repeat'] = c.post(url, json={'transition_id': 'convert'}).status_code
        out['final_counts'] = counts()
    """)
    assert out['initial_counts'] == [1, 0, 0, 0], out
    assert out['contacted_code'] == 200 and out['contacted']['status'] == 'Contacted', out
    assert out['contacted']['converted_account_id'] and out['contacted']['converted_contact_id'], out
    assert out['contacted']['converted_deal_id'] is None, out
    assert out['after_contact'] == [1, 1, 1, 0], out
    assert out['after_contact_stage'] == 'Contacted' and out['after_contact_edges'] == ['Qualify'], out
    assert out['qualified_code'] == 200 and out['qualified']['status'] == 'Qualified', out
    assert out['qualified']['converted_deal_id'] is None, out
    assert out['after_qualify'] == [1, 1, 1, 0] and out['after_qualify_edges'] == ['Convert'], out
    assert out['bypass_patch'] == 409 and out['bypass_api'] == 409, out
    assert out['before_convert'] == [1, 1, 1, 0], out
    assert out['converted_code'] == 200 and out['converted']['status'] == 'Converted', out
    assert out['converted']['converted_deal_id'] and out['deal']['origin_lead_id'] == out['converted']['id'], out
    assert out['deal']['account_id'] == out['converted']['converted_account_id'], out
    assert out['deal']['contact_id'] == out['converted']['converted_contact_id'], out
    assert out['after_convert'] == [0, 1, 1, 1], out
    assert out['terminal_edges'] == [] and out['repeat'] == 422, out
    assert out['final_counts'] == [0, 1, 1, 1], out


def test_lead_detail_conversion_message_requires_created_deal():
    js = (ROOT / 'static/js/app.js').read_text(encoding='utf-8')
    assert 'const converted = current === "Converted" && record.status === "Converted" && Boolean(record.converted_deal_id)' in js
    assert 'No outgoing transitions from this stage in the published Blueprint.' in js
    assert 'View created Deal' in js
    assert '&& !timeline?.blueprint_enabled' in js
    assert 'toast("Lead converted","Account, Contact and Deal records are now linked.")' in js
