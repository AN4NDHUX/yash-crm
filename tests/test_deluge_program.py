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
