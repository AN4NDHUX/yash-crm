"""End-to-end API contract for visual Blueprint draft, publish and transition."""
from pathlib import Path
from test_workflow_rule_builder import app_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_visual_blueprint_frontend_is_wired():
    app = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
    designer = (ROOT / "static/js/features/blueprints.js").read_text(encoding="utf-8")
    assert 'createBlueprintFeature' in app and 'blueprintFeature.view()' in app
    assert 'blueprintDealProgress(record,timeline)' in app
    assert 'data-blueprint-move=' in app
    assert 'data-bp-canvas' in designer
    assert 'data-bp-phase' in designer
    assert 'Save as Draft' in designer and 'Publish Blueprint' in designer


def test_visual_blueprint_draft_publish_and_tenant_safe_transition():
    out = app_scenario("""
    with TestClient(main.app) as client:
        signup = client.post('/api/auth/signup', json={
            'name':'Visual Blueprint Owner','organization_name':'Visual Blueprint Org',
            'username':'visual.blueprint','email':'visual.blueprint@example.com',
            'password':'strong-password-123'})
        assert signup.status_code in (200, 201), signup.text
        lead = client.post('/api/leads', json={'name':'Visual Blueprint Lead'}).json()
        payload = {'name':'Contact process','module':'Leads','layout_name':'Default',
            'field_name':'status','entry_conditions':[],
            'stages':[{'id':'new','label':'New','x':100,'y':100},
                      {'id':'contacted','label':'Contacted','x':380,'y':100}],
            'transitions':[{'id':'t1','label':'Establish contact','from':'New',
                'to':'Contacted','owner_scope':'any','required':[],'after':[]}]}
        created = client.post('/api/blueprint-designer',json=payload)
        out['create'] = created.status_code
        data = created.json()
        out['draft_status'] = (data.get('draft'),data.get('active'))
        out['draft_timeline'] = client.get(f"/api/leads/{lead['id']}/timeline").json().get('blueprint_enabled')
        blueprint_id = data['id']
        publish = client.post(f'/api/blueprint-designer/{blueprint_id}/publish')
        out['publish'] = publish.status_code
        timeline = client.get(f"/api/leads/{lead['id']}/timeline").json()
        out['matched'] = timeline.get('blueprint_enabled')
        out['name'] = timeline.get('blueprint_name')
        out['choices'] = timeline.get('transition_details')
        out['states'] = timeline.get('blueprint_states')
        out['wrong_jump'] = client.patch(f"/api/leads/{lead['id']}",json={'status':'Qualified'}).status_code
        change = client.post(f"/api/blueprint-records/leads/{lead['id']}/transition",
                             json={'transition_id':'t1','fields':{}})
        out['transition'] = change.status_code
        out['current'] = client.get(f"/api/leads/{lead['id']}").json().get('status')
        out['next_choices'] = client.get(f"/api/leads/{lead['id']}/timeline").json().get('transition_details')
        out['mismatched_record'] = client.post(f"/api/blueprint-records/deals/{lead['id']}/transition",
                                              json={'transition_id':'t1'}).status_code
    """)
    assert out['create'] == 201, out
    assert out['draft_status'] == [True, False], out
    assert out['draft_timeline'] is False, out
    assert out['publish'] == 200, out
    assert out['matched'] is True, out
    assert out['name'] == 'Contact process', out
    assert out['states'] == ['New','Contacted'], out
    assert out['choices'][0]['label'] == 'Establish contact', out
    assert out['wrong_jump'] == 422, out
    assert out['transition'] == 200, out
    assert out['current'] == 'Contacted', out
    assert out['next_choices'] == [], out
    assert out['mismatched_record'] in (404, 409), out

def test_criteria_options_are_field_specific_and_organization_scoped():
    out = app_scenario("""
    with TestClient(main.app) as first:
        signup = first.post('/api/auth/signup', json={
            'name':'Criteria First','organization_name':'Criteria First Org',
            'username':'criteria.first','email':'criteria.first@example.com',
            'password':'strong-password-123'})
        assert signup.status_code in (200, 201), signup.text
        lead = first.post('/api/leads', json={
            'name':'Criteria Test Lead','company':'Aster Dynamics Unique',
            'source':'Partner Event'} )
        assert lead.status_code in (200, 201), lead.text
        lead_meta_response = first.get('/api/blueprint-designer/options?module=leads')
        out['lead_code'] = lead_meta_response.status_code
        out['first_lead'] = lead_meta_response.json()
        deal_meta_response = first.get('/api/blueprint-designer/options?module=deals')
        out['deal_code'] = deal_meta_response.status_code
        out['first_deal'] = deal_meta_response.json()
        invalid = first.get('/api/blueprint-designer/options?module=contacts')
        out['invalid'] = invalid.status_code
    with TestClient(main.app) as second:
        signup = second.post('/api/auth/signup', json={
            'name':'Criteria Second','organization_name':'Criteria Second Org',
            'username':'criteria.second','email':'criteria.second@example.com',
            'password':'strong-password-123'})
        assert signup.status_code in (200, 201), signup.text
        options_response = second.get('/api/blueprint-designer/options?module=leads')
        out['second_code'] = options_response.status_code
        out['second_values'] = options_response.json()['criteria_meta']['company']['options']
    """)
    assert out['lead_code'] == 200 and out['deal_code'] == 200, out
    assert out['invalid'] == 422, out
    lead = out['first_lead']['criteria_meta']
    deal = out['first_deal']['criteria_meta']
    assert lead['status']['type'] == 'select', out
    assert {'New', 'Contacted', 'Qualified', 'Unqualified'} <= set(lead['status']['options']), out
    assert {'Website', 'Referral', 'LinkedIn'} <= set(lead['source']['options']), out
    assert 'Partner Event' in lead['source']['options'], out
    assert lead['company']['allow_custom'] is True, out
    assert 'Aster Dynamics Unique' in lead['company']['options'], out
    assert lead['lead_score']['type'] == 'number', out
    assert {'Qualification', 'Proposal', 'Closed Won'} <= set(deal['stage']['options']), out
    assert deal['status']['type'] == 'select', out
    assert out['second_code'] == 200, out
    assert 'Aster Dynamics Unique' not in out['second_values'], out


def test_blueprint_criteria_value_select_is_bound_to_metadata():
    js = (ROOT / "static/js/features/blueprints.js").read_text(encoding="utf-8")
    assert 'criteriaValue(condition)' in js
    assert 'opts?.criteria_meta?.[field]' in js
    assert 'name="value_choice"' in js
    assert 'name="value_custom"' in js
    assert 'node.name==="field" || node.name==="operator"' in js


def test_visual_blueprint_designer_and_transition_isolated_across_organizations():
    result = app_scenario("""
    with TestClient(main.app) as first:
        signup = first.post('/api/auth/signup', json={
            'name':'Blueprint Tenant A','organization_name':'Blueprint Tenant A Org',
            'username':'blueprint.tenant.a','email':'blueprint.tenant.a@example.com',
            'password':'strong-password-123'
        })
        out['first_signup'] = signup.status_code
        lead = first.post('/api/leads', json={'name':'Tenant A Blueprint Lead'})
        out['lead'] = lead.status_code
        lead_id = lead.json()['id']
        payload = {
            'name':'Tenant A private stages','module':'Leads','layout_name':'Default',
            'field_name':'status','entry_conditions':[],
            'stages':[{'id':'new','label':'New','x':0,'y':0},
                      {'id':'contacted','label':'Contacted','x':100,'y':0}],
            'transitions':[{'id':'move','label':'Contact lead','from':'New',
                            'to':'Contacted','owner_scope':'any','required':[],'after':[]}]
        }
        created = first.post('/api/blueprint-designer', json=payload)
        out['created'] = created.status_code
        blueprint_id = created.json()['id']
        with TestClient(main.app) as second:
            signup = second.post('/api/auth/signup', json={
                'name':'Blueprint Tenant B','organization_name':'Blueprint Tenant B Org',
                'username':'blueprint.tenant.b','email':'blueprint.tenant.b@example.com',
                'password':'strong-password-123'
            })
            out['second_signup'] = signup.status_code
            list_result = second.get('/api/blueprint-designer')
            out['list'] = list_result.status_code
            out['visible_ids'] = [row['id'] for row in list_result.json()['items']]
            out['detail'] = second.get(f'/api/blueprint-designer/{blueprint_id}').status_code
            out['publish'] = second.post(f'/api/blueprint-designer/{blueprint_id}/publish').status_code
            out['edit'] = second.put(f'/api/blueprint-designer/{blueprint_id}', json=payload).status_code
            out['transition'] = second.post(
                f'/api/blueprint-records/leads/{lead_id}/transition',
                json={'transition_id':'move','fields':{}}
            ).status_code
    """)
    assert result['first_signup'] in (200, 201), result
    assert result['second_signup'] in (200, 201), result
    assert result['lead'] in (200, 201), result
    assert result['created'] == 201, result
    assert result['list'] == 200, result
    assert result['visible_ids'] == [], result
    assert all(result[key] == 404 for key in ('detail', 'publish', 'edit', 'transition')), result
