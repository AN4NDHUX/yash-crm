from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_filters_script(script: str) -> dict:
    body = (
        "import base64, json\n"
        "from fastapi.testclient import TestClient\n"
        "import app.main as main\n"
        "auth = {'Authorization':'Basic ' + base64.b64encode(b'admin:supersecretpass123').decode()}\n"
        "out = {}\n" + textwrap.dedent(script) + "\nprint('RESULT' + json.dumps(out))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{tmp}/filters.db",
            "ENABLE_AUTH": "true", "APP_USERNAME": "admin",
            "APP_PASSWORD": "supersecretpass123", "ADMIN_EMAIL": "admin@example.com",
            "SEED_DEMO_DATA": "false", "PYTHONPATH": str(ROOT),
        })
        process = subprocess.run([sys.executable, "-c", body], cwd=ROOT, env=env,
                                 capture_output=True, text=True, timeout=120)
    assert process.returncode == 0, process.stderr[-5000:]
    line = [s for s in process.stdout.splitlines() if s.startswith("RESULT")][-1]
    return json.loads(line[6:])


def test_module_filter_catalogs_and_authorized_field_criteria():
    out = run_filters_script("""
        with TestClient(main.app) as c:
            def make(resource, data):
                result = c.post('/api/' + resource, json=data, headers=auth)
                assert result.status_code in (200,201), (resource,result.text)
                return result.json()
            alpha = make('accounts', {'name':'Filter Alpha','industry':'Technology'})
            beta = make('accounts', {'name':'Filter Beta','industry':'Retail'})
            contact = make('contacts', {'first_name':'Filter','last_name':'Linked','account_id':alpha['id']})
            lone = make('contacts', {'first_name':'Filter','last_name':'Unlinked'})
            deal = make('deals', {'name':'Filter Large','amount':8750,'stage':'Proposal','account_id':alpha['id']})
            lost = make('deals', {'name':'Filter Lost','amount':10,'stage':'Closed Lost','account_id':beta['id']})
            lead = make('leads', {'name':'Filter Fresh','status':'New'})
            def filtered(module,rules,join='all',limit=25):
                return c.get('/api/'+module,headers=auth,params={
                    'limit':limit,'filters':json.dumps({'join':join,'rules':rules})
                })
            def field(key,op,value):
                return {'kind':'field','key':key,'operator':op,'value':value}
            def related(key,op,value=''):
                return {'kind':'related','key':key,'operator':op,'value':value}
            def system(key):
                return {'kind':'system','key':key,'operator':'enabled','value':''}
            out['catalog'] = {}
            for module in ('leads','deals','accounts','contacts'):
                response = c.get('/api/module-filter-options/'+module,headers=auth)
                out['catalog'][module] = (
                    response.status_code == 200 and
                    bool(response.json()['fields']) and bool(response.json()['related'])
                    and bool(response.json()['system'])
                )
            out['names'] = [r['id'] for r in filtered('accounts',[field('name','contains','alpha')]).json()['items']]
            out['numeric'] = [r['id'] for r in filtered('deals',[field('amount','gte','8000')]).json()['items']]
            out['status'] = [r['id'] for r in filtered('deals',[system('closed')]).json()['items']]
            out['by_contact'] = [r['id'] for r in filtered('accounts',[related('contacts','exists','Linked')]).json()['items']]
            # Keep diagnostically useful tenant/link metadata in assertion output.
            from app.services.module_filtering import _same_org, _matches_link
            from app.models import Account, Contact
            from app.database import SessionLocal
            with SessionLocal() as inspect_db:
                parent = inspect_db.get(Account, alpha['id'])
                child = inspect_db.get(Contact, contact['id'])
                out['relationship_debug'] = {
                    'account': {field: getattr(parent, field) for field in ('id', 'owner_id', 'organization_id')},
                    'contact': {field: getattr(child, field) for field in ('id', 'owner_id', 'organization_id', 'account_id')},
                    'same_org': _same_org(parent, child),
                    'linked': _matches_link(parent, 'accounts', child, 'contacts'),
                    'record_api': {'account_id': contact.get('account_id'), 'organization_id': contact.get('organization_id')},
                }
            out['without_contact'] = [r['id'] for r in filtered('accounts',[related('contacts','not_exists')]).json()['items']]
            out['contacts_by_account'] = [r['id'] for r in filtered('contacts',[related('accounts','exists','Alpha')]).json()['items']]
            out['contacts_without_account'] = [r['id'] for r in filtered('contacts',[related('accounts','not_exists')]).json()['items']]
            out['deals_by_account'] = [r['id'] for r in filtered('deals',[related('accounts','exists','Alpha')]).json()['items']]
            out['all_join'] = [r['id'] for r in filtered('accounts',[field('name','contains','Filter'), related('contacts','exists')]).json()['items']]
            out['any_join'] = [r['id'] for r in filtered('accounts',[field('name','contains','Beta'), related('contacts','exists')],join='any',limit=100).json()['items']]
            out['paged'] = filtered('accounts',[field('name','contains','Filter')],limit=1).json()
            out['no_results'] = filtered('leads',[field('name','contains','No match')]).json()['total']
            out['bad_field'] = filtered('leads',[field('password_hash','contains','secret')]).status_code
            out['bad_relation'] = filtered('leads',[related('invoices','exists')]).status_code
            out['bad_date'] = filtered('leads',[field('created_at','gte','bad-date')]).status_code
            out['too_many'] = filtered('leads',[field('name','contains','a')]*13).status_code
            out['bad_json'] = c.get('/api/leads',headers=auth,params={'filters':'not-json'}).status_code
            out['anonymous_catalog'] = c.get('/api/module-filter-options/accounts').status_code
            out['unknown_catalog'] = c.get('/api/module-filter-options/products',headers=auth).status_code
            out['ids'] = {'alpha':alpha['id'],'beta':beta['id'],'contact':contact['id'],
                         'lone':lone['id'],'deal':deal['id'],'lost':lost['id'],'lead':lead['id']}
    """)
    assert all(out['catalog'].values()), out
    ids = out['ids']
    assert out['names'] == [ids['alpha']], out
    assert ids['deal'] in out['numeric'] and ids['lost'] not in out['numeric'], out
    assert ids['lost'] in out['status'] and ids['deal'] not in out['status'], out
    assert out['by_contact'] == [ids['alpha']], json.dumps(out, sort_keys=True)
    assert ids['beta'] in out['without_contact'] and ids['alpha'] not in out['without_contact'], out
    assert out['contacts_by_account'] == [ids['contact']], out
    assert ids['lone'] in out['contacts_without_account'] and ids['contact'] not in out['contacts_without_account'], out
    assert out['deals_by_account'] == [ids['deal']], out
    assert ids['alpha'] in out['all_join'] and ids['beta'] not in out['all_join'], out
    assert ids['alpha'] in out['any_join'] and ids['beta'] in out['any_join'], out
    assert out['paged']['total'] == 2 and len(out['paged']['items']) == 1, out
    assert out['no_results'] == 0, out
    for name in ('bad_field','bad_relation','bad_date','too_many','bad_json'):
        assert out[name] == 422, (name,out)
    assert out['anonymous_catalog'] in (401,403), out
    assert out['unknown_catalog'] == 404, out


def test_module_filter_file_sources_wired_to_core_lists():
    app = (ROOT / 'static/js/app.js').read_text(encoding='utf-8')
    assert 'bindModuleFilters({resource, current, renderRoute, toast})' in app
    assert 'params.set("filters", JSON.stringify(current.advancedFilters))' in app
    assert 'renderModuleFilters(resource, current, current.filterCatalog, esc)' in app
    filters = (ROOT / 'static/js/features/module-filters.js').read_text(encoding='utf-8')
    for text in ('System Defined Filters','Filter By Fields','Filter By Related Modules'):
        assert text in filters
    assert 'data-filter-apply' in filters and 'data-filter-reset' in filters


def test_related_filters_enforce_organization_isolation_and_legacy_ownership():
    from types import SimpleNamespace
    from app.services.module_filtering import _same_org

    def record(org, owner):
        return SimpleNamespace(organization_id=org, owner_id=owner)

    assert _same_org(record(4, 2), record(4, 3))
    assert not _same_org(record(4, 2), record(5, 2))
    assert not _same_org(record(4, 2), record(None, 2))
    assert not _same_org(record(None, 2), record(4, 2))
    assert _same_org(record(None, 2), record(None, 2))
    assert not _same_org(record(None, 2), record(None, 3))
    assert not _same_org(record(None, None), record(None, None))
