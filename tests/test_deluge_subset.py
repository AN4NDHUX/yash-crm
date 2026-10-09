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


def test_deluge_notification_and_record_reference():
    steps = parse_deluge('crm.notify("Review this lead");\ncrm.createTask($record.name);')
    assert steps == [
        {"type": "notification", "value": "Review this lead"},
        {"type": "create_task", "subject": "$record.name"},
    ]


def test_deluge_conditional_actions_compile():
    source = 'if ($record.status == "Qualified") {\ncrm.addTag("Reviewed");\n}'
    assert parse_deluge(source) == [{
        "type": "tag", "value": "Reviewed",
        "_conditions": [{"field": "status", "operator": "==", "value": "Qualified"}],
    }]


@pytest.mark.parametrize("source", [
    'if ($record.password == "secret") {\ncrm.addTag("Unsafe");\n}',
    'if ($record.status == "Qualified") {\ncrm.addTag("Open");',
    '}\ncrm.addTag("Unexpected");',
])
def test_deluge_rejects_invalid_condition_blocks(source):
    with pytest.raises(HTTPException):
        parse_deluge(source)


def test_deluge_literal_collection_for_each_loop():
    source = 'for each item in ["Hot", "Warm"] {\ncrm.addTag($item);\n}'
    assert parse_deluge(source) == [
        {"type": "tag", "value": "Hot"},
        {"type": "tag", "value": "Warm"},
    ]


@pytest.mark.parametrize("source", [
    'for each item in [1,2] {\ncrm.addTag($item);\n}',
    'for each item in ["ok"] {\ncrm.addTag($item);',
    'for each item in ["ok"] {\nwhile(true) {\ncrm.addTag($item);\n}\n}',
    'for each item in ' + str(["x"] * 21).replace("'", '"') + ' {\ncrm.addTag($item);\n}',
])
def test_deluge_rejects_unbounded_or_invalid_collections(source):
    with pytest.raises(HTTPException):
        parse_deluge(source)


def test_deluge_nested_bounded_collections_and_conditions():
    source = (
        'for each group in ["North", "South"] {\n'
        'if ($record.status == "Qualified") {\n'
        'for each tag in ["Hot", "Warm"] {\n'
        'crm.addTag($tag);\n'
        '}\n'
        '}\n'
        '}'
    )
    steps = parse_deluge(source)
    assert len(steps) == 4
    assert [step["value"] for step in steps] == ["Hot", "Warm", "Hot", "Warm"]
    assert all(step["_conditions"] == [
        {"field": "status", "operator": "==", "value": "Qualified"}
    ] for step in steps)


def test_deluge_loop_substitution_respects_identifier_boundaries():
    with pytest.raises(HTTPException):
        parse_deluge(
            'for each item in ["safe"] {\n'
            'crm.addTag($item_suffix);\n'
            '}'
        )


def test_deluge_nested_loop_action_budget_is_enforced():
    source = (
        'for each outer in ["a", "b", "c", "d", "e"] {\n'
        'for each inner in ["a", "b", "c", "d", "e"] {\n'
        'crm.addTag($inner);\n'
        '}\n'
        '}'
    )
    with pytest.raises(HTTPException) as error:
        parse_deluge(source)
    assert error.value.status_code == 422
