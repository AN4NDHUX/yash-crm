"""Guided CRM import regression: formats, mapping, dedupe, history and tenant-safe writes."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.import_wizard import parse_import_file
from test_workflow_rule_builder import app_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_csv_excel_and_vcard_readers():
    csv_file = parse_import_file("leads.csv", b"Full Name,Phone Number\nAva Smith,+919876543210\n")
    assert csv_file["columns"] == ["Full Name", "Phone Number"]
    assert csv_file["rows"][0]["Phone Number"] == "+919876543210"
    assert parse_import_file("contacts.vcf", (
        b"BEGIN:VCARD\nVERSION:3.0\nFN:Ava Smith\nTEL;TYPE=CELL:+919876543210\nEMAIL:ava@example.test\nEND:VCARD\n"
    ))["rows"][0]["Phone"] == "+919876543210"

    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["Full Name", "Phone Number"])
    wb.active.append(["Ava Smith", "+919876543210"])
    buffer = io.BytesIO()
    wb.save(buffer)
    excel = parse_import_file("leads.xlsx", buffer.getvalue())
    assert excel["count"] == 1
    assert excel["rows"][0]["Phone Number"] == "+919876543210"
    with pytest.raises(HTTPException):
        parse_import_file("fake.xls", b"Not an Excel workbook")
    with pytest.raises(HTTPException):
        parse_import_file("malware.exe", b"Executable")


def test_ui_contracts_and_setup_entries():
    app = (ROOT / "static/js/app.js").read_text()
    wizard = (ROOT / "static/js/features/import-wizard.js").read_text()
    catalog = (ROOT / "app/platform_catalog.py").read_text()
    for module in ("leads", "deals", "accounts", "contacts"):
        assert f'/api/import-wizard/' in wizard
        assert f'["leads", "deals", "accounts", "contacts"]' in app
        assert f'["leads", "deals", "accounts", "contacts"]' in wizard
    assert 'data-start-import' in app
    assert 'Phone Number must be mapped' in (ROOT / "app/main.py").read_text()
    for item in ('("import","Import")', '("import_history","Import History")',
                 '("export","Export")', '("recycle_bin","Recycle Bin")'):
        assert item in catalog
    assert '"phone"' in (ROOT / "static/js/features/modules.js").read_text()


def test_wizard_endpoints_for_four_modules_and_mandatory_phone_mapping():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        signup = c.post('/api/auth/signup', json={
            'name':'Import Admin','organization_name':'Import Test Workspace',
            'username':'guided.import.admin','email':'guided.import@example.com',
            'password':'strong-password-123'
        })
        out['signup'] = signup.status_code
        out['modules'] = {}
        for module in ('leads','deals','accounts','contacts'):
            name_field = 'first_name' if module=='contacts' else 'name'
            name_header = 'First Name' if module=='contacts' else 'Name'
            payload = (name_header+',Phone Number\\nTest-'+module+',+918888111222\\n').encode()
            mapping = {name_header:name_field,'Phone Number':'phone'}
            files = [('files',('data.csv',payload,'text/csv'))]
            preview = c.post('/api/import-wizard/'+module+'/preview',files=files)
            missing = c.post('/api/import-wizard/'+module+'/submit',files=files,
                data={'mapping':json.dumps({name_header:name_field})})
            submit = c.post('/api/import-wizard/'+module+'/submit',files=files,
                data={'mapping':json.dumps(mapping),'duplicate_key':'phone'})
            again = c.post('/api/import-wizard/'+module+'/submit',files=files,
                data={'mapping':json.dumps(mapping),'duplicate_key':'phone'})
            listed = c.get('/api/'+module+'?search=Test-'+module)
            out['modules'][module] = {
                'preview':preview.status_code,
                'columns':preview.json().get('columns'),
                'invalid':missing.status_code,
                'status':submit.status_code,
                'created':submit.json().get('imported'),
                'repeat_status':again.status_code,
                'repeat_skipped':again.json().get('skipped'),
                'total':listed.json().get('total')
            }
        hist = c.get('/api/import-jobs')
        out['history'] = hist.status_code
        out['history_count'] = len(hist.json().get('items',[]))
    """)
    assert out["signup"] in {200, 201, 302, 303}
    assert out["history"] == 200
    assert out["history_count"] >= 8
    for module, result in out["modules"].items():
        assert result["preview"] == 200, (module, result)
        assert result["columns"] in (["Name", "Phone Number"], ["First Name", "Phone Number"])
        assert result["invalid"] == 422, (module, result)
        assert result["status"] == 200, (module, result)
        assert result["created"] == 1, (module, result)
        assert result["repeat_status"] == 200
        assert result["repeat_skipped"] == 1
        assert result["total"] == 1


def test_guided_import_update_and_blank_phone_rejected():
    out = app_scenario("""
    with TestClient(main.app, follow_redirects=False) as c:
        c.post('/api/auth/signup', json={
            'name':'Update Admin','organization_name':'Update Import Workspace',
            'username':'guided.update.admin','email':'guided.update@example.com',
            'password':'strong-password-123'
        })
        original = c.post('/api/leads', json={'name':'Original', 'phone':'+919900001122'}).json()
        update_data = b'Name,Phone Number\\nUpdated,+919900001122\\n'
        update = c.post('/api/import-wizard/leads/submit',
            files=[('files',('update.csv',update_data,'text/csv'))],
            data={'mapping':json.dumps({'Name':'name','Phone Number':'phone'}),
                'operation':'update','duplicate_key':'phone'})
        out['status'] = update.status_code
        out['updated'] = update.json().get('updated')
        out['name'] = c.get('/api/leads/'+str(original['id'])).json().get('name')
        no_phone = c.post('/api/import-wizard/leads/submit',
            files=[('files',('blank.csv',b'Name,Phone Number\\nBad,\\n','text/csv'))],
            data={'mapping':json.dumps({'Name':'name','Phone Number':'phone'})})
        out['errors'] = len(no_phone.json().get('errors',[]))
        out['blank_status'] = no_phone.status_code
    """)
    assert out == {'status':200,'updated':1,'name':'Updated','errors':1,'blank_status':200}
