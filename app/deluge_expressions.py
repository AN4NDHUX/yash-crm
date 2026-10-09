"""Bounded, side-effect-free Deluge expression subset for CRM workflows.

This is deliberately not a Python sandbox. It interprets an explicit AST
allowlist, never executes arbitrary Python or makes network requests.
"""
from __future__ import annotations

import ast
import copy
import operator
import re
from fastapi import HTTPException

MAX_EXPRESSION = 2048
MAX_NODES = 100
PROTECTED = {"password", "password_hash", "organization_id", "id", "owner_id", "created_by"}
BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod,
}
COMPARE = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
}
ALLOWED_METHODS = {"get", "size", "containsKey", "contains", "isEmpty", "toString", "put", "add", "remove", "keys", "values", "getKeys", "getValues", "distinct", "sort", "reverse", "subList", "toUpperCase", "toLowerCase", "trim", "startsWith", "endsWith", "replaceAll", "indexOf"}



def normalize_deluge_expression(source: str) -> str:
    """Translate Deluge boolean tokens outside quoted literals only."""
    quoted = re.split(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', source)
    for index in range(0, len(quoted), 2):
        part = quoted[index]
        part = re.sub(r'\$record\.([A-Za-z][A-Za-z0-9_]{0,79})', r'record.\1', part)
        part = re.sub(r'\btrue\b', "True", part)
        part = re.sub(r'\bfalse\b', "False", part)
        part = re.sub(r'\bnull\b', "None", part)
        part = part.replace("&&", " and ").replace("||", " or ")
        quoted[index] = re.sub(r'!(?!=)', " not ", part)
    return "".join(quoted).strip()


def evaluate_deluge_expression(source: str, record: dict | None = None):
    if not isinstance(source, str) or len(source) > MAX_EXPRESSION:
        raise HTTPException(422, "Deluge expression exceeds supported limit")
    normalized = normalize_deluge_expression(source)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(422, "Unsupported Deluge expression syntax") from exc
    if len(list(ast.walk(tree))) > MAX_NODES:
        raise HTTPException(422, "Deluge expression is too complex")
    snapshot = copy.deepcopy(dict(record or {}))

    def interpret(node, depth=0):
        if depth > 20:
            raise HTTPException(422, "Expression depth exceeded")
        def read(part):
            return interpret(part, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
            return node.value
        if isinstance(node, ast.List):
            return [read(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return [read(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            result = {read(k): read(v) for k, v in zip(node.keys, node.values)}
            if not all(isinstance(key, str) for key in result):
                raise HTTPException(422, "Map keys must be strings")
            return result
        if isinstance(node, ast.Name) and node.id == "record":
            return snapshot
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "record":
                if node.attr.startswith("_") or node.attr.lower() in PROTECTED:
                    raise HTTPException(422, "Protected record field")
                return snapshot.get(node.attr)
            raise HTTPException(422, "Attribute access is not supported")
        if isinstance(node, ast.Subscript):
            target, key = read(node.value), read(node.slice)
            if isinstance(target, dict) and isinstance(key, str):
                if key.startswith("_") or key.lower() in PROTECTED:
                    raise HTTPException(422, "Protected key")
                return target.get(key)
            if isinstance(target, list) and isinstance(key, int) and -len(target) <= key < len(target):
                return target[key]
            raise HTTPException(422, "Invalid collection index")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
            value = read(node.operand)
            if isinstance(node.op, ast.Not):
                return not bool(value)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(422, "Numeric operand required")
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            left, right = read(node.left), read(node.right)
            if type(node.op) is ast.Add and isinstance(left, str) and isinstance(right, str):
                value = left + right
            elif any(isinstance(n, bool) or not isinstance(n, (int, float)) for n in (left, right)):
                raise HTTPException(422, "Numeric operands required")
            else:
                try:
                    value = BINARY[type(node.op)](left, right)
                except (ZeroDivisionError, OverflowError) as exc:
                    raise HTTPException(422, "Invalid arithmetic operation") from exc
            if isinstance(value, (int, float)) and abs(value) > 1e12 or isinstance(value, str) and len(value) > 1000:
                raise HTTPException(422, "Expression result too large")
            return value
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            if isinstance(node.op, ast.And):
                return all(read(item) for item in node.values)
            return any(read(item) for item in node.values)
        if isinstance(node, ast.Compare):
            left = read(node.left)
            for op, part in zip(node.ops, node.comparators):
                right = read(part)
                if type(op) not in COMPARE:
                    raise HTTPException(422, "Comparison operator not supported")
                try:
                    matched = COMPARE[type(op)](left, right)
                except TypeError as exc:
                    raise HTTPException(422, "Incompatible comparison") from exc
                if not matched:
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and not node.keywords:
            if isinstance(node.func, ast.Name) and node.func.id in {"List", "Map"} and not node.args:
                return [] if node.func.id == "List" else {}
            if isinstance(node.func, ast.Attribute) and node.func.attr in ALLOWED_METHODS:
                target = read(node.func.value)
                args = [read(arg) for arg in node.args]
                method = node.func.attr
                if method in {"put", "add", "remove"}:
                    # Mutations are only allowed on expressions constructing fresh
                    # collections; never on record-backed or nested references.
                    def ephemeral(node):
                        if isinstance(node, (ast.List, ast.Dict)):
                            return True
                        return (isinstance(node, ast.Call) and
                                (isinstance(node.func, ast.Name) and node.func.id in {"Map", "List"} or
                                 isinstance(node.func, ast.Attribute) and node.func.attr in {"put", "add", "remove"} and ephemeral(node.func.value)))
                    if not ephemeral(node.func.value):
                        raise HTTPException(422, "Collection mutation requires a new collection")
                    if method == "put" and isinstance(target, dict) and len(args) == 2 and isinstance(args[0], str):
                        if args[0].startswith("_") or args[0].lower() in PROTECTED or len(target) >= 100:
                            raise HTTPException(422, "Invalid map key or capacity")
                        target[args[0]] = args[1]
                        return target
                    if method == "add" and isinstance(target, list) and len(args) == 1:
                        if len(target) >= 100:
                            raise HTTPException(422, "List capacity exceeded")
                        target.append(args[0])
                        return target
                    if method == "remove" and len(args) == 1:
                        if isinstance(target, dict) and isinstance(args[0], str):
                            if args[0].startswith("_") or args[0].lower() in PROTECTED:
                                raise HTTPException(422, "Protected key")
                            target.pop(args[0], None)
                            return target
                        if isinstance(target, list) and type(args[0]) is int and 0 <= args[0] < len(target):
                            target.pop(args[0])
                            return target
                if method in {"getKeys", "getValues"} and isinstance(target, dict) and not args:
                    return list(target.keys() if method == "getKeys" else target.values())
                if method == "distinct" and isinstance(target, list) and not args:
                    unique = []
                    for item in target:
                        if item not in unique:
                            unique.append(item)
                    return unique
                if method == "reverse" and isinstance(target, list) and not args:
                    return list(reversed(target))
                if method == "sort" and isinstance(target, list) and not args:
                    if not all(type(item) is str for item in target) and not all(type(item) in {int, float} for item in target):
                        raise HTTPException(422, "List sort requires uniform strings or numbers")
                    return sorted(target)
                if method == "subList" and isinstance(target, list) and len(args) == 2 and all(type(a) is int for a in args):
                    start, end = args
                    if not 0 <= start <= end <= len(target):
                        raise HTTPException(422, "Invalid list slice")
                    return target[start:end]
                if isinstance(target, str):
                    if method in {"toUpperCase", "toLowerCase", "trim"} and not args:
                        return {"toUpperCase": str.upper, "toLowerCase": str.lower, "trim": str.strip}[method](target)
                    if method in {"startsWith", "endsWith"} and len(args) == 1 and isinstance(args[0], str):
                        return target.startswith(args[0]) if method == "startsWith" else target.endswith(args[0])
                    if method == "indexOf" and len(args) == 1 and isinstance(args[0], str):
                        return target.find(args[0])
                    if method == "replaceAll" and len(args) == 2 and all(isinstance(a, str) for a in args):
                        if not args[0]:
                            raise HTTPException(422, "Empty replacement pattern")
                        result = target.replace(args[0], args[1])
                        if len(result) > 1000:
                            raise HTTPException(422, "Expression result too large")
                        return result
                if method in {"keys", "values"} and isinstance(target, dict) and not args:
                    return list(target.keys() if method == "keys" else target.values())
                if method == "size" and not args and isinstance(target, (dict, list, str)):
                    return len(target)
                if method == "isEmpty" and not args and isinstance(target, (dict, list, str)):
                    return len(target) == 0
                if method == "toString" and not args and isinstance(target, (str, int, float, bool)):
                    return str(target)
                if method == "get" and len(args) == 1 and isinstance(target, dict) and isinstance(args[0], str):
                    if args[0].startswith("_") or args[0].lower() in PROTECTED:
                        raise HTTPException(422, "Protected key")
                    return target.get(args[0])
                if method == "get" and len(args) == 1 and isinstance(target, list) and type(args[0]) is int and 0 <= args[0] < len(target):
                    return target[args[0]]
                if method == "containsKey" and len(args) == 1 and isinstance(target, dict):
                    return args[0] in target
                if method == "contains" and len(args) == 1 and isinstance(target, (list, str)):
                    return args[0] in target
            raise HTTPException(422, "Unsupported Deluge function or method")
        raise HTTPException(422, "Unsupported Deluge expression")

    return interpret(tree.body)
