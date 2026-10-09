"""Structured, budgeted Deluge control-flow interpreter for workflow functions.

The supported grammar is deliberately explicit. No Python eval, imports,
reflection, unbounded loops, filesystem or direct HTTP access.
"""
from __future__ import annotations

import re
from fastapi import HTTPException
from app.deluge_expressions import evaluate_deluge_expression, normalize_deluge_expression
from app.deluge_subset import parse_deluge

NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
RESERVED = {"record", "crm", "if", "else", "for", "while", "true", "false", "null"}
MAX_NODES = 100
MAX_DEPTH = 6
MAX_OPERATIONS = 200
MAX_ACTIONS = 20


def _lines(source):
    if not isinstance(source, str) or not source.strip() or len(source.encode("utf-8")) > 32768:
        raise HTTPException(422, "Deluge source must contain 1 to 32 KiB of text")
    output = []
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "{":
            if not output or output[-1].endswith("{"):
                raise HTTPException(422, "Unexpected opening brace")
            output[-1] += " {"
        elif line.startswith("} else "):
            output.append("}")
            output.append(line[2:].strip())
        else:
            output.append(line)
    return output


def _validate_expression(expression):
    from ast import parse
    try:
        parse(normalize_deluge_expression(expression), mode="eval")
    except (SyntaxError, ValueError) as error:
        raise HTTPException(422, "Invalid Deluge expression") from error
    if len(expression) > 2048:
        raise HTTPException(422, "Deluge expression exceeds limit")
    return expression


def compile_deluge_program(source):
    """Return structured statements. Braces may be placed on the header line or on the following line."""
    lines = _lines(source)
    position = 0
    count = 0

    def read_block(depth=0, inside_loop=False):
        nonlocal position, count
        if depth > MAX_DEPTH:
            raise HTTPException(422, "Deluge nesting depth exceeded")
        result = []
        while position < len(lines):
            line = lines[position]
            if line == "}":
                position += 1
                return result, True
            if line.startswith("else"):
                raise HTTPException(422, "Else without preceding if")
            if count >= MAX_NODES:
                raise HTTPException(422, "Deluge program too complex")
            count += 1
            position += 1
            conditional = re.fullmatch(r"if\s*\((.+)\)\s*\{", line)
            if conditional:
                branches = []
                body, closed = read_block(depth + 1, inside_loop)
                if not closed:
                    raise HTTPException(422, "Unclosed if block")
                branches.append((_validate_expression(conditional.group(1)), body))
                other = []
                while position < len(lines):
                    elseif = re.fullmatch(r"else\s+if\s*\((.+)\)\s*\{", lines[position])
                    if elseif:
                        position += 1
                        branch, closed = read_block(depth + 1, inside_loop)
                        if not closed:
                            raise HTTPException(422, "Unclosed else-if block")
                        branches.append((_validate_expression(elseif.group(1)), branch))
                        continue
                    if lines[position] == "else {":
                        position += 1
                        other, closed = read_block(depth + 1, inside_loop)
                        if not closed:
                            raise HTTPException(422, "Unclosed else block")
                    break
                result.append({"kind": "if", "branches": branches, "else": other})
                continue
            each = re.fullmatch(r"for\s+each\s+([A-Za-z][A-Za-z0-9_]{0,39})\s+in\s+(.+)\s*\{", line)
            if each:
                variable, source_expr = each.groups()
                if variable in RESERVED:
                    raise HTTPException(422, "Reserved loop variable")
                body, closed = read_block(depth + 1, True)
                if not closed:
                    raise HTTPException(422, "Unclosed for-each block")
                result.append({"kind": "foreach", "name": variable, "collection": _validate_expression(source_expr.strip()), "body": body})
                continue
            loop = re.fullmatch(r"while\s*\((.+)\)\s*\{", line)
            if loop:
                body, closed = read_block(depth + 1, True)
                if not closed:
                    raise HTTPException(422, "Unclosed while block")
                result.append({"kind": "while", "condition": _validate_expression(loop.group(1)), "body": body})
                continue
            if line in {"break;", "continue;"}:
                if not inside_loop:
                    raise HTTPException(422, "Loop control outside loop")
                result.append({"kind": line[:-1]})
                continue
            if line == "return;" or line.startswith("return "):
                if not line.endswith(";"):
                    raise HTTPException(422, "Return requires semicolon")
                expression = line[7:-1].strip() if line != "return;" else None
                result.append({"kind": "return", "expression": _validate_expression(expression) if expression else None})
                continue
            if not line.endswith(";"):
                raise HTTPException(422, "Deluge statement must end with a semicolon")
            statement = line[:-1].strip()
            assignment = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]{0,39})\s*=\s*(.+)", statement)
            if assignment:
                name, expression = assignment.groups()
                if name in RESERVED:
                    raise HTTPException(422, "Reserved Deluge variable")
                result.append({"kind": "assign", "name": name, "expression": _validate_expression(expression)})
                continue
            mutation = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]{0,39})\.(add|put|remove)\((.*)\)", statement)
            if mutation:
                name, method, argument_text = mutation.groups()
                if name in RESERVED:
                    raise HTTPException(422, "Reserved mutation target")
                # Parse arguments as a tuple without allowing general Python calls.
                args = _validate_expression("(" + argument_text + ",)")
                result.append({"kind": "mutate", "name": name, "method": method, "args": args})
                continue
            if statement.startswith("info "):
                result.append({"kind": "action", "action": parse_deluge("info = " + statement[5:] + ";")[0]})
                continue
            # Delegate approved CRM action validation to the existing fail-closed parser.
            action = parse_deluge(line)[0]
            result.append({"kind": "action", "action": action})
        return result, False

    program, closed = read_block()
    if closed:
        raise HTTPException(422, "Unexpected closing brace")
    if not program:
        raise HTTPException(422, "Empty Deluge program")
    return program


class _Flow(Exception):
    def __init__(self, kind):
        self.kind = kind


def execute_deluge_program(program, record, action_handler):
    """Run prevalidated statements, with strict CPU and action budgets."""
    variables = {}
    operations = 0
    actions = 0

    def evaluate(expression):
        try:
            return evaluate_deluge_expression(expression, record, variables)
        except HTTPException as exc:
            raise ValueError("Deluge expression rejected") from exc

    def run(nodes, depth=0):
        nonlocal operations, actions
        if depth > MAX_DEPTH:
            raise ValueError("Deluge nesting budget exceeded")
        for node in nodes:
            operations += 1
            if operations > MAX_OPERATIONS:
                raise ValueError("Deluge execution budget exceeded")
            kind = node["kind"]
            if kind == "assign":
                name = node["name"]
                if name not in variables and len(variables) >= 40:
                    raise ValueError("Deluge variable budget exceeded")
                variables[name] = evaluate(node["expression"])
                continue
            if kind == "mutate":
                name, method = node["name"], node["method"]
                if name not in variables:
                    raise ValueError("Undefined Deluge collection")
                args = evaluate(node["args"])
                target = variables[name]
                if method == "add" and type(target) is list and len(args) == 1 and len(target) < 100:
                    target.append(args[0])
                elif method == "put" and type(target) is dict and len(args) == 2 and type(args[0]) is str and len(target) < 100:
                    from app.deluge_expressions import PROTECTED
                    if args[0].startswith("_") or args[0].lower() in PROTECTED:
                        raise ValueError("Protected map key")
                    target[args[0]] = args[1]
                elif method == "remove" and type(target) is list and len(args) == 1 and type(args[0]) is int and 0 <= args[0] < len(target):
                    target.pop(args[0])
                elif method == "remove" and type(target) is dict and len(args) == 1 and type(args[0]) is str:
                    from app.deluge_expressions import PROTECTED
                    if args[0].startswith("_") or args[0].lower() in PROTECTED:
                        raise ValueError("Protected map key")
                    target.pop(args[0], None)
                else:
                    raise ValueError("Unsupported collection mutation")
                continue
            if kind == "if":
                for condition, branch in node["branches"]:
                    if bool(evaluate(condition)):
                        run(branch, depth + 1)
                        break
                else:
                    run(node["else"], depth + 1)
                continue
            if kind in {"foreach", "while"}:
                if kind == "foreach":
                    collection = evaluate(node["collection"])
                    if type(collection) not in {list, dict} or len(collection) > 100:
                        raise ValueError("Invalid Deluge loop collection")
                    iterable = list(collection)
                else:
                    iterable = range(MAX_OPERATIONS)
                for item in iterable:
                    if kind == "while" and not bool(evaluate(node["condition"])):
                        break
                    if kind == "foreach":
                        variables[node["name"]] = item
                    try:
                        run(node["body"], depth + 1)
                    except _Flow as signal:
                        if signal.kind == "break":
                            break
                        if signal.kind == "continue":
                            continue
                        raise
                else:
                    if kind == "while" and bool(evaluate(node["condition"])):
                        raise ValueError("Deluge while loop iteration budget exceeded")
                continue
            if kind in {"return", "break", "continue"}:
                raise _Flow(kind)
            if kind == "action":
                actions += 1
                if actions > MAX_ACTIONS:
                    raise ValueError("Deluge CRM action budget exceeded")
                action_handler(node["action"], variables)
                continue
            raise ValueError("Unrecognized Deluge program instruction")
    try:
        run(program)
    except _Flow as signal:
        if signal.kind != "return":
            raise ValueError("Invalid loop control escape")
    return variables
