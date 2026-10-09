"""CRM lead state, deal ribbon and timeline contracts."""
from pathlib import Path
import re
from test_workflow_rule_builder import app_scenario

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static/js/app.js").read_text(encoding="utf-8")


def test_record_ui_stage_and_timeline_controls_are_connected():
    assert re.search(r'function\s+leadStagePanel\s*\(\s*record\s*,\s*timeline\s*\)', JS)
    assert 'function timelineHtml(events)' in JS
    assert 'function dealProgress(record)' in JS
    assert 'data-lead-transition=' in JS
    assert 'data-stage-update=' in JS
    assert 'data-blueprint-move=' in JS
    assert 'blueprintDealProgress(record,timeline)' in JS
    assert 'data-timeline-kind=' in JS
    assert 'data-timeline-filter' in JS
    assert '/timeline' in JS
    assert 'data-platform-create="site_visits"' not in JS
    assert 'Customer journey' not in JS
    assert 'crm-pipeline-step is-current' not in JS  # dynamic classes, not static.


def test_timeline_records_stage_changes_and_rejects_cross_tenant_access():
    out = app_scenario("""
    with TestClient(main.app) as first:
        signup = first.post('/api/auth/signup', json={
            'name':'Timeline First','organization_name':'Timeline First Org',
            'username':'timeline.first','email':'timeline.first@example.com',
            'password':'strong-password-123'})
        assert signup.status_code in (200,201), signup.text
        lead = first.post('/api/leads', json={'name':'Lead timeline audit'}).json()
        deal = first.post('/api/deals', json={'name':'Deal timeline audit'}).json()
        changed_lead = first.patch(f"/api/leads/{lead['id']}", json={'status':'Contacted'})
        changed_deal = first.patch(f"/api/deals/{deal['id']}", json={'stage':'Proposal'})
        out['lead_patch'] = changed_lead.status_code
        out['deal_patch'] = changed_deal.status_code
        lead_history = first.get(f"/api/leads/{lead['id']}/timeline")
        deal_history = first.get(f"/api/deals/{deal['id']}/timeline")
        out['lead_code'] = lead_history.status_code
        out['deal_code'] = deal_history.status_code
        out['lead_history'] = lead_history.json()
        out['deal_history'] = deal_history.json()
        out['unknown_resource'] = first.get(f"/api/contacts/{lead['id']}/timeline").status_code
        out['missing_record'] = first.get('/api/leads/99999999/timeline').status_code
        out['other_tenant'] = {}
        with TestClient(main.app) as second:
            registration = second.post('/api/auth/signup', json={
                'name':'Timeline Second','organization_name':'Timeline Second Org',
                'username':'timeline.second','email':'timeline.second@example.com',
                'password':'strong-password-123'})
            assert registration.status_code in (200,201), registration.text
            out['other_tenant']['lead'] = second.get(f"/api/leads/{lead['id']}/timeline").status_code
            out['other_tenant']['deal'] = second.get(f"/api/deals/{deal['id']}/timeline").status_code
    """)
    assert out['lead_patch'] == 200, out
    assert out['deal_patch'] == 200, out
    assert out['lead_code'] == 200 and out['deal_code'] == 200, out
    assert any('Status changed from New to Contacted' in item['title'] for item in out['lead_history']['items']), out
    assert any('Stage changed from Qualification to Proposal' in item['title'] for item in out['deal_history']['items']), out
    for history in ('lead_history', 'deal_history'):
        assert not any('before' in event or 'after' in event for event in out[history]['items'])
    assert out['unknown_resource'] == 404
    assert out['missing_record'] == 404
    assert out['other_tenant'] == {'lead': 404, 'deal': 404}


def test_lead_blueprint_transitions_are_listed_and_enforced():
    out = app_scenario("""
    with TestClient(main.app) as client:
        registered = client.post('/api/auth/signup', json={
            'name':'Blueprint Lead Owner','organization_name':'Lead Stage Policy Org',
            'username':'blueprint.lead','email':'blueprint.lead@example.com',
            'password':'strong-password-123'})
        assert registered.status_code in (200,201), registered.text
        lead = client.post('/api/leads', json={'name':'Blueprint controlled lead'}).json()
        with main.SessionLocal() as db:
            db.add(main.Blueprint(
                organization_id=lead['organization_id'],
                name='Lead Stage Rules', module='Leads',
                active=True, archived=False,
                transitions=[{'from':'New','to':'Contacted'},
                             {'from':'Contacted','to':'Qualified'}],
            ))
            db.commit()
        initial = client.get(f"/api/leads/{lead['id']}/timeline")
        out['configured'] = initial.json().get('blueprint_enabled')
        out['first_options'] = initial.json().get('transitions')
        out['blocked'] = client.patch(f"/api/leads/{lead['id']}", json={'status':'Qualified'}).status_code
        out['accepted'] = client.patch(f"/api/leads/{lead['id']}", json={'status':'Contacted'}).status_code
        out['next_options'] = client.get(f"/api/leads/{lead['id']}/timeline").json().get('transitions')
        out['current_status'] = client.get(f"/api/leads/{lead['id']}").json().get('status')
    """)
    assert out['configured'] is True, out
    assert out['first_options'] == ['Contacted'], out
    assert out['blocked'] == 422, out
    assert out['accepted'] == 200, out
    assert out['current_status'] == 'Contacted', out
    assert out['next_options'] == ['Qualified'], out

def test_visual_blueprint_canvas_connection_controls_are_real():
    source = (ROOT / "static/js/features/blueprints.js").read_text(encoding="utf-8")
    assert "function connectStates(fromIndex,toIndex)" in source
    assert 'data-bp-connect=' in source
    assert 'data-bp-edge=' in source
    assert 'graphLabels()' in source
    assert 'data-bp="cancel-link"' in source
    assert 'if(connectingFrom!==null){connectStates(connectingFrom,n);return;}' in source
    assert "connectStates(link.from,Number(node.dataset.bpState))" in source
    assert "draft.transitions.some(e=>e.from===from&&e.to===to)" in source
    assert "if(fromIndex===toIndex)" in source
