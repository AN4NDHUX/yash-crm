"""Read-only preflight for the independent CONVOSIS workflow worker.

Checks against the same database and migration head used by the CRM web app.
It deliberately does not claim jobs, send HTTP, or modify any records.
"""
from __future__ import annotations

import json
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text

from app.database import SessionLocal, engine
from app.models import WorkflowExecution
import app.workflow_worker  # noqa: F401 - fail if worker imports cannot be resolved

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = {
    "id", "organization_id", "status", "actions", "attempts",
    "locked_at", "next_attempt_at", "idempotency_key",
}


def verify_worker_readiness() -> dict:
    config = Config(str(ROOT / "alembic.ini"))
    expected = ScriptDirectory.from_config(config).get_current_head()
    if not expected:
        raise RuntimeError("Alembic does not have an unambiguous migration head")
    with SessionLocal() as db:
        db.execute(text("SELECT 1")).scalar_one()
        revisions = set(db.scalars(text("SELECT version_num FROM alembic_version")).all())
        if revisions != {expected}:
            raise RuntimeError(
                f"Worker DB schema does not match migration head: actual={sorted(revisions)}, expected={expected}"
            )
        columns = {column["name"] for column in inspect(db.get_bind()).get_columns("workflow_executions")}
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise RuntimeError("Workflow queue is missing required columns: " + ", ".join(missing))
        db.execute(select(WorkflowExecution.id).limit(1)).first()
    return {"status": "ready", "database": engine.dialect.name,
            "migration_revision": expected, "queue_schema": "ready",
            "worker_import": "ready"}


if __name__ == "__main__":
    print(json.dumps(verify_worker_readiness(), sort_keys=True))
