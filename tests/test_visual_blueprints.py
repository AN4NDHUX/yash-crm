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
