"""Static validation for user-authored CRM Python functions.

This is NOT an execution sandbox. Validated scripts must never be executed
inside the web process. Runtime isolation and capability-scoped CRM APIs are
required before enabling execution.
"""
from __future__ import annotations

import ast

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


def validate_function_source(values: dict) -> None:
    """Validate script drafts; retain the existing declarative step-list format."""
    if str(values.get("runtime", "")).lower() != "python":
        return
    source = values.get("source")
    if isinstance(source, list):
        return  # Existing declarative workflow executor validates step types.
    if not isinstance(source, dict):
        raise FunctionValidationError("Python source must be a step list or code object")
    validate_python_source(source.get("code"))
