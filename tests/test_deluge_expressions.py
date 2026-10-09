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
