"""Safe Deluge expression subset and CRM binding regression tests."""
import pytest
from fastapi import HTTPException
from app.deluge_expressions import evaluate_deluge_expression
from app.deluge_subset import parse_deluge


def test_deluge_arithmetic_boolean_and_record_expressions():
    evaluate = evaluate_deluge_expression
    assert evaluate("1 + 2 * 3") == 7
    assert evaluate("(8 / 2) >= 4 and true") is True
    assert evaluate('$record.amount * 2 + 5', {"amount": 10}) == 25
    steps = parse_deluge('record.put("score", = $record.amount * 2 + 5);')
    assert steps == [{"type": "field_update", "field": "score", "value": {"$deluge_expr": "$record.amount * 2 + 5"}}]


def test_deluge_list_and_map_expression_methods():
    evaluate = evaluate_deluge_expression
    assert evaluate('["one", "two"].size()') == 2
    assert evaluate('["one", "two"].contains("two")') is True
    assert evaluate('{"name":"Lead"}.get("name")') == "Lead"
    assert evaluate('{"name":"Lead"}.containsKey("name")') is True
    assert evaluate('Map().isEmpty()') is True
    assert evaluate('List().size()') == 0


@pytest.mark.parametrize("source", [
    '__import__("os").system("id")', 'open("/etc/passwd")',
    '$record.password', '$record.organization_id',
    '{"password":"secret"}.get("password")', 'Map().__class__',
    '[1,2,3][100]', '1 / 0', '2 ** 1000000',
])
def test_deluge_expressions_fail_closed(source):
    with pytest.raises(HTTPException) as exc:
        evaluate_deluge_expression(source, {"password": "secret", "organization_id": 2})
    assert exc.value.status_code == 422


def test_deluge_external_tasks_are_not_accidentally_executable():
    with pytest.raises(HTTPException):
        parse_deluge('invokeurl ["url":"https://example.com","type":GET];')


def test_compound_deluge_if_compiles_to_checked_expression():
    steps = parse_deluge(
        'if ($record.amount > 100 && $record.stage != "Closed") {\n'
        'crm.addTag("Priority");\n'
        '}'
    )
    assert steps[0]["_conditions"] == [
        {"expression": '$record.amount > 100 && $record.stage != "Closed"'}
    ]
    assert evaluate_deluge_expression(
        steps[0]["_conditions"][0]["expression"],
        {"amount": 250, "stage": "Open"},
    ) is True
    assert evaluate_deluge_expression("!false && true") is True


def test_deluge_bounded_ephemeral_collection_mutations():
    evaluate = evaluate_deluge_expression
    assert evaluate('Map().put("name", "Lead").get("name")') == "Lead"
    assert evaluate('List().add("Hot").add("Warm").size()') == 2
    assert evaluate('["a","b"].remove(0)') == ["b"]
    assert evaluate('{"a":1}.put("b", 2).keys()') == ["a", "b"]
    assert evaluate('{"a":1}.values()') == [1]


def test_deluge_record_collection_mutation_is_denied():
    with pytest.raises(HTTPException):
        evaluate_deluge_expression('$record.tags.add("untrusted")', {"tags": ["safe"]})
    with pytest.raises(HTTPException):
        evaluate_deluge_expression('$record.data.put("owner_id", 3)', {"data": {"name": "safe"}})


def test_zoho_style_update_record_is_current_record_only():
    source = 'zoho.crm.updateRecord("Leads", $record.id, {"status":"Qualified","lead_score":80});'
    assert parse_deluge(source) == [{
        "type": "crm_update_current",
        "module": "Leads",
        "fields": {"status": "Qualified", "lead_score": 80},
    }]
    for invalid in (
        'zoho.crm.updateRecord("Leads", 999, {"status":"Qualified"});',
        'zoho.crm.updateRecord("Leads", $record.id, {"organization_id":8});',
        'zoho.crm.updateRecord("Leads", $record.id, {});',
    ):
        with pytest.raises(HTTPException):
            parse_deluge(invalid)
