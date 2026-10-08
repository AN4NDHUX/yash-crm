"""Restricted Deluge-style workflow actions; no eval, imports, loops or network access.

Supported statements (one per line):
    record.put("status", "Qualified");
    crm.addTag("Reviewed");
    crm.createTask("Follow up");
    crm.notify("Follow-up required");
    info "Audit message";
Only literal strings and $record.field references are accepted as values.
"""
import json
import re
from fastapi import HTTPException

MAX_BYTES = 32768
FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
STATEMENT = re.compile(r"^(record\.put|crm\.addTag|crm\.createTask|crm\.notify)\((.*)\)$")
REFERENCE = re.compile(r"^\$record\.([A-Za-z][A-Za-z0-9_]{0,79})$")
PROTECTED = {"password", "password_hash", "organization_id", "id", "owner_id", "created_by"}


def _argument(token):
    token = token.strip()
    if REFERENCE.fullmatch(token):
        field = token[8:]
        if field.lower() in PROTECTED:
            raise HTTPException(422, "Protected record reference")
        return token
    try:
        value = json.loads(token)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Only quoted strings or $record.field references are supported") from exc
    if not isinstance(value, str) or len(value) > 1000:
        raise HTTPException(422, "Argument must be a string of at most 1000 characters")
    return value



def _expand_literal_loops(source):
    """Expand small literal-list for-each blocks before parsing CRM statements.

    A loop must have its opening and closing braces on separate lines.
    Literal list values are JSON strings. Expansion is capped to 20 actions.
    """
    lines = source.splitlines()
    result = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = re.fullmatch(
            r'for each ([A-Za-z][A-Za-z0-9_]{0,39}) in (\[.*\])\s*\{', line
        )
        if not match:
            result.append(lines[index])
            index += 1
            continue
        variable, literal = match.groups()
        try:
            values = json.loads(literal)
        except ValueError as exc:
            raise HTTPException(422, "Loop collection must be a JSON string list") from exc
        if not isinstance(values, list) or len(values) > 20 or any(
            not isinstance(value, str) or len(value) > 1000 for value in values
        ):
            raise HTTPException(422, "Loop collection must contain at most 20 strings")
        body = []
        index += 1
        while index < len(lines) and lines[index].strip() != "}":
            if "{" in lines[index] or "}" in lines[index]:
                raise HTTPException(422, "Nested loop or condition blocks are not supported inside for each")
            body.append(lines[index])
            index += 1
        if index == len(lines):
            raise HTTPException(422, "Unclosed for each loop")
        if len(body) * len(values) + len(result) > 100:
            raise HTTPException(422, "Loop expansion exceeds execution budget")
        for value in values:
            for statement in body:
                result.append(statement.replace("$" + variable, json.dumps(value)))
        index += 1
    return "\n".join(result)


def parse_deluge(source):
    if not isinstance(source, str) or not source.strip() or len(source.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(422, "Deluge source must contain 1 to 32 KiB of text")
    source = _expand_literal_loops(source)
    steps = []
    condition_stack = []
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line == "}":
            if not condition_stack:
                raise HTTPException(422, f"Line {line_number}: unexpected closing brace")
            condition_stack.pop()
            continue
        conditional = re.fullmatch(r'if\s*\(\s*(\$record\.[A-Za-z][A-Za-z0-9_]{0,79})\s*(==|!=)\s*("[^"]{0,1000}")\s*\)\s*\{', line)
        if conditional:
            field_reference, operator, literal = conditional.groups()
            _argument(field_reference)
            condition_stack.append({"field": field_reference[8:], "operator": operator, "value": _argument(literal)})
            if len(condition_stack) > 5:
                raise HTTPException(422, "Maximum conditional nesting is five")
            continue
        if not line.endswith(";"):
            raise HTTPException(422, f"Line {line_number}: statement must end with a semicolon")
        line = line[:-1].strip()
        if line.startswith("info "):
            steps.append({"type": "audit", "value": _argument(line[5:])})
        else:
            match = STATEMENT.fullmatch(line)
            if not match:
                raise HTTPException(422, f"Line {line_number}: unsupported Deluge statement")
            command, arguments = match.groups()
            if command == "record.put":
                parts = re.fullmatch(r'\s*("(?:[^"\\]|\\.)*")\s*,\s*(.*?)\s*', arguments)
                if not parts:
                    raise HTTPException(422, f"Line {line_number}: record.put requires field and value")
                field = _argument(parts.group(1))
                if not FIELD.fullmatch(field) or field.lower() in PROTECTED or field.startswith("_"):
                    raise HTTPException(422, f"Line {line_number}: invalid or protected field")
                steps.append({"type": "field_update", "field": field, "value": _argument(parts.group(2))})
            elif command == "crm.addTag":
                steps.append({"type": "tag", "value": _argument(arguments)})
            elif command == "crm.createTask":
                steps.append({"type": "create_task", "subject": _argument(arguments)})
            else:
                steps.append({"type": "notification", "value": _argument(arguments)})
        if condition_stack:
            steps[-1]["_conditions"] = [dict(condition) for condition in condition_stack]
        if len(steps) > 20:
            raise HTTPException(422, "Deluge functions support at most 20 statements")
    if condition_stack:
        raise HTTPException(422, "Unclosed if block")
    if not steps:
        raise HTTPException(422, "Deluge function requires at least one statement")
    return steps
