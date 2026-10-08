"""Regression tests for custom function source validation.

Validation is a preflight check, not an execution sandbox.
"""
import pytest

from app.custom_function_validation import (
    FunctionValidationError,
    MAX_SOURCE_BYTES,
    validate_python_source,
)


@pytest.mark.parametrize("source", [
    "result = record['id']",
    "total = 0\nfor value in [1, 2, 3]:\n    total += value",
    "def calculate(value):\n    return value * 2",
])
def test_accepts_supported_python(source):
    result = validate_python_source(source)
    assert result["bytes"] > 0
    assert result["ast_nodes"] > 0


@pytest.mark.parametrize("source", [
    "",
    "   ",
    "def bad(:\n    pass",
    "import os",
    "from pathlib import Path",
    "exec('print(1)')",
    "open('/etc/passwd')",
    "obj.__class__",
    "obj._private",
    "globals()",
    "class Unsafe: pass",
    "with something: pass",
    "async def unsafe(): pass",
    "try:\n    pass\nexcept Exception:\n    pass",
])
def test_rejects_unsupported_or_dangerous_source(source):
    with pytest.raises(FunctionValidationError):
        validate_python_source(source)


def test_rejects_non_string():
    with pytest.raises(FunctionValidationError):
        validate_python_source(None)


def test_rejects_oversized_source():
    with pytest.raises(FunctionValidationError, match="32 KiB"):
        validate_python_source("x = '" + ("a" * MAX_SOURCE_BYTES) + "'")


def test_rejects_excessive_ast_complexity():
    source = "\n".join("x = 1" for _ in range(700))
    with pytest.raises(FunctionValidationError, match="too complex"):
        validate_python_source(source)


def test_python_script_draft_accepted_and_active_rejected():
    from fastapi import HTTPException
    from app.custom_function_validation import validate_function_source

    payload = {"runtime": "Python", "source": {"code": "result = record['id']"}, "status": "Inactive"}
    assert validate_function_source(payload) is None
    payload["status"] = "Active"
    with pytest.raises(HTTPException) as error:
        validate_function_source(payload)
    assert error.value.status_code == 422


def test_legacy_declarative_steps_remain_compatible():
    from app.custom_function_validation import validate_function_source

    payload = {"runtime": "Python", "entrypoint": "steps", "status": "Active",
               "source": [{"type": "field_update", "field": "company", "value": "Normalized"}]}
    assert validate_function_source(payload) is None


def test_malformed_python_source_returns_422():
    from fastapi import HTTPException
    from app.custom_function_validation import validate_function_source

    for source in (None, "invalid", {"code": "import os"}, {"code": ""}):
        with pytest.raises(HTTPException) as error:
            validate_function_source({"runtime": "Python", "source": source, "status": "Inactive"})
        assert error.value.status_code == 422
