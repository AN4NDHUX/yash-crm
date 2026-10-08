"""Executable restricted Deluge workflow tests."""
import pytest
from fastapi import HTTPException

from app.deluge_subset import parse_deluge
from app.custom_function_validation import validate_function_source


def test_deluge_compiles_approved_crm_operations():
    steps = parse_deluge('record.put("status", "Qualified");\ncrm.addTag("Reviewed");\ncrm.createTask("Follow up");\ninfo "Logged";')
    assert [step["type"] for step in steps] == ["field_update", "tag", "create_task", "audit"]
    validate_function_source({
        "runtime": "Deluge", "status": "Active",
        "source": {"code": 'crm.addTag("Reviewed");', "language": "Deluge"},
    })


@pytest.mark.parametrize("source", [
    'import java.io.File;',
    'crm.invokeUrl("https://example.com");',
    'record.put("organization_id", "other");',
    'record.put("password", "secret");',
    'while(true) {}',
    'crm.addTag($record.password);',
    'crm.addTag("ok")',
    'crm.addTag("ok");\n' * 21,
])
def test_deluge_rejects_unsupported_or_dangerous_code(source):
    with pytest.raises(HTTPException) as exc:
        validate_function_source({"runtime": "Deluge", "status": "Active", "source": {"code": source}})
    assert exc.value.status_code == 422


def test_python_remains_unexecutable():
    with pytest.raises(HTTPException):
        validate_function_source({"runtime": "Python", "status": "Active", "source": {"code": "print(1)"}})
