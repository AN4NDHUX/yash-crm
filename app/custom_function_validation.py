"""Static validation for user-authored CRM Python functions.

This is NOT an execution sandbox. Validated scripts must never be executed
inside the web process. Runtime isolation and capability-scoped CRM APIs are
required before enabling execution.
"""
from __future__ import annotations

import ast
from fastapi import HTTPException

MAX_SOURCE_BYTES = 32_768
MAX_AST_NODES = 2_000
FORBIDDEN = (
    ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
    ast.ClassDef, ast.AsyncFunctionDef, ast.Lambda,
    ast.With, ast.AsyncWith, ast.Try, ast.Raise,
    ast.Delete, ast.Yield, ast.YieldFrom, ast.Await,
)
FORBIDDEN_NAMES = {
    "__builtins__", "__import__", "eval", "exec", "compile", "open",
    "input", "globals", "locals", "vars", "dir", "getattr",
    "setattr", "delattr", "breakpoint", "memoryview",
}


class FunctionValidationError(ValueError):
    """User-authored function failed static validation."""


def validate_python_source(source: str) -> dict[str, int]:
    if not isinstance(source, str) or not source.strip():
        raise FunctionValidationError("Function source must be nonempty text")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise FunctionValidationError("Function source exceeds 32 KiB")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise FunctionValidationError(
            f"Syntax error at line {exc.lineno}: {exc.msg}"
        ) from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise FunctionValidationError("Function is too complex")
    for node in nodes:
        if isinstance(node, FORBIDDEN):
            raise FunctionValidationError(
                f"Unsupported construct: {type(node).__name__}"
            )
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise FunctionValidationError(f"Forbidden name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise FunctionValidationError("Private attribute access is forbidden")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise FunctionValidationError("Dunder identifiers are forbidden")
    return {"bytes": len(source.encode("utf-8")), "ast_nodes": len(nodes)}


DECLARATIVE_ACTIONS = {
    "field_update", "update_field", "create_task", "task",
    "notification", "notify", "tag", "audit",
}
MAX_DECLARATIVE_STEPS = 20


def validate_declarative_steps(source: list) -> None:
    """Validate the workflow executor's approved action language at save time."""
    if not 1 <= len(source) <= MAX_DECLARATIVE_STEPS:
        raise HTTPException(422, "Function requires between 1 and 20 approved steps")
    for index, step in enumerate(source, start=1):
        if not isinstance(step, dict):
            raise HTTPException(422, f"Function step {index} must be an object")
        action = str(step.get("type", "")).lower()
        if action not in DECLARATIVE_ACTIONS:
            raise HTTPException(422, f"Function step {index} has an unsupported action")
        if action in {"field_update", "update_field"} and not str(step.get("field", "")).strip():
            raise HTTPException(422, f"Function step {index} requires a field")


def validate_function_source(values: dict) -> None:
    """Fail closed on executable scripts until a separately isolated worker exists.

    Only approved declarative steps can be Active. Static Python validation
    does not grant execution permission, and selecting another runtime must
    not bypass this boundary.
    """
    runtime = str(values.get("runtime") or "Python").strip().lower()
    source = values.get("source")
    status = str(values.get("status") or "Inactive").strip().lower()

    if runtime not in {"python", "javascript", "http"}:
        raise HTTPException(422, "Unsupported custom function runtime")

    if isinstance(source, list) or (
        isinstance(source, dict) and isinstance(source.get("steps"), list)
    ):
        if runtime != "python":
            raise HTTPException(422, "Declarative steps require the Python runtime")
        steps = source if isinstance(source, list) else source["steps"]
        validate_declarative_steps(steps)
        return

    if status == "active":
        raise HTTPException(
            422, "Executable custom functions require an isolated execution worker"
        )

    if runtime != "python":
        raise HTTPException(
            422, "Only Python draft source is currently supported"
        )
    if not isinstance(source, dict) or "steps" in source:
        raise HTTPException(422, "Python source must be a step list or code object")
    try:
        validate_python_source(source.get("code"))
    except FunctionValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
