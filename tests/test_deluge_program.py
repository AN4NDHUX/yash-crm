"""Bounded Deluge program control-flow tests."""
import pytest
from fastapi import HTTPException
from app.deluge_program import compile_deluge_program, execute_deluge_program


def execute(source, record=None):
    actions = []
    def callback(action, vars):
        actions.append((action, dict(vars)))
    vars = execute_deluge_program(compile_deluge_program(source), record or {}, callback)
    return actions, vars


def test_variable_collections_for_each_and_mutations():
    actions, vars = execute("""
tags = List();
tags.add("Hot");
tags.add("Warm");
count = 0;
for each tag in tags {
    count = count + 1;
    crm.addTag(tag);
}
""")
    assert [action["value"] for action, _ in actions] == [
        {"$deluge_expr": "tag"}, {"$deluge_expr": "tag"}
    ]
    assert [snapshot["tag"] for _, snapshot in actions] == ["Hot", "Warm"]
    assert vars["count"] == 2


def test_while_else_if_break_continue_and_return():
    actions, vars = execute("""
number = 0;
while (number < 10) {
    number = number + 1;
    if (number == 1) {
        continue;
    } else if (number == 2) {
        crm.addTag("second");
    } else {
        break;
    }
}
return;
crm.addTag("unreachable");
""")
    assert len(actions) == 1
    assert actions[0][0]["value"] == "second"
    assert vars["number"] == 3


def test_map_operations_and_protected_fields():
    _, vars = execute("""
settings = Map();
settings.put("level", "High");
level = settings.get("level");
""")
    assert vars["level"] == "High"
    with pytest.raises((HTTPException, ValueError)):
        execute('settings = Map();\nsettings.put("organization_id", 3);')


@pytest.mark.parametrize("source", [
    "while (true) {\n}",
    "break;",
    "continue;",
    'record = "overwrite";',
    "x = open('/etc/passwd');",
    "while (true) {\ncrm.addTag(\"repeat\");\n}",
])
def test_program_rejects_unsafe_or_unbounded_actions(source):
    with pytest.raises((HTTPException, ValueError)):
        execute(source)


def test_identity_data_not_visible_via_record_map_iteration():
    actions, vars = execute("""
fields = record.keys();
count = fields.size();
""", {"organization_id": 8, "password": "secret", "name": "Visible"})
    assert vars["count"] == 1


def test_separate_braces_and_else_if_blocks():
    actions, variables = execute("""
score = 10;
if (score > 50)
{
  crm.addTag("High");
}
else if (score > 5)
{
  crm.addTag("Medium");
}
else
{
  crm.addTag("Low");
}
""")
    assert len(actions) == 1
    assert actions[0][0]["value"] == "Medium"


def test_record_put_is_crm_action_not_map_mutation():
    actions, variables = execute("""
value = "Qualified";
record.put("status", value);
""")
    assert len(actions) == 1
    assert actions[0][0]["type"] == "field_update"
    assert actions[0][0]["field"] == "status"
    assert actions[0][0]["value"] == {"$deluge_expr": "value"}
    assert actions[0][1]["value"] == "Qualified"


def test_zoho_crm_tasks_support_result_variables_and_bounded_invocation():
    program = compile_deluge_program("""
result = zoho.crm.v8.getRecordById("Leads", 12);
matches = zoho.crm.v8.searchRecords("Leads", "(name:equals:A)");
zoho.crm.v8.updateRecord("Leads", 12, {"company":"Updated"});
""")
    result = []
    def task_handler(task, expression, variables):
        result.append((task, expression, dict(variables)))
        return {"id": 12, "name": "A"}
    actions = []
    variables = execute_deluge_program(program, {}, lambda action, v: actions.append(action), task_handler)
    assert [task for task, _, _ in result] == ["getRecordById", "searchRecords", "updateRecord"]
    assert variables["result"]["id"] == 12
    assert variables["matches"]["name"] == "A"


def test_deluge_bracket_invokeurl_never_returns_fake_http_response():
    program = compile_deluge_program("""
delivery = invokeurl
[
    url: "https://api.example.com/v1/notify"
    type: POST
    connection: "partner"
    body: {"event": "new-lead"}
];
""")
    result = []
    def send(expression, variables):
        result.append(expression)
        return {"status": "queued", "execution_id": 47}
    variables = execute_deluge_program(program, {}, lambda action, vars: None,
                                      http_handler=send)
    assert len(result) == 1
    assert variables["delivery"] == {"status":"queued", "execution_id":47}


@pytest.mark.parametrize("source", [
    'x = invokeurl\n[\n url: "http://localhost"\n type: GET\n];',
    'x = invokeurl\n[\n url: "https://example.com"\n type: GET\n connection: "partner"\n url: "https://evil.com"\n];',
    'x = invokeurl\n[\n url: "https://example.com"\n type: GET\n connection: "partner"\n',
])
def test_invokeurl_rejects_missing_connection_duplicate_url_or_unclosed_map(source):
    with pytest.raises(HTTPException):
        compile_deluge_program(source)


def test_integration_tasks_in_loops_have_runtime_budget():
    program = compile_deluge_program("""
counter = 0;
while (counter < 21) {
    counter = counter + 1;
    zoho.crm.v8.getRecords("Leads");
}
""")
    calls = []
    with pytest.raises(ValueError, match="integration call budget"):
        execute_deluge_program(program, {}, lambda action, vars: None,
            lambda task, args, vars: calls.append(task))
    assert len(calls) == 20
