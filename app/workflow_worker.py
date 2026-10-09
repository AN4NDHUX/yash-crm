"""Dedicated workflow worker: python -m app.workflow_worker.

Run as a separate Railway service against the same PostgreSQL database.
A database lease prevents concurrent workers from claiming the same execution.
External delivery is at-least-once: downstream recipients should honor the
X-CRM-Idempotency-Key header, because a crash after HTTP success but before
commit may cause redelivery.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from sqlalchemy import or_, select

from app.database import SessionLocal, TENANT_ACTOR_ID, TENANT_ORGANIZATION_ID
from app.models import WorkflowExecution, PlatformRecord
from app.services.core import RESOURCE_MAP, _execute_workflow_action, add_audit

log = logging.getLogger("workflow-worker")
MAX_ATTEMPTS = 5
LEASE_SECONDS = 300


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _send_external(action: dict, execution: WorkflowExecution) -> None:
    kind = str(action.get("type") or "").lower()
    if kind == "deluge_http":
        from app.deluge_http import send_deluge_http
        send_deluge_http(action, execution)
        return
    if kind == "email":
        recipient = str(action.get("to") or "").strip()
        approved = {x.strip().lower() for x in os.getenv("WORKFLOW_EMAIL_RECIPIENTS", "").split(",") if x.strip()}
        if not recipient or recipient.lower() not in approved:
            raise ValueError("Recipient is not permitted by WORKFLOW_EMAIL_RECIPIENTS")
        host = os.getenv("WORKFLOW_SMTP_HOST", "")
        sender = os.getenv("WORKFLOW_EMAIL_FROM", "")
        if not host or not sender:
            raise ValueError("Workflow SMTP is not configured")
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = str(action.get("subject") or "CRM workflow notification")[:180]
        message.set_content(str(action.get("body") or action.get("value") or "")[:20000])
        with smtplib.SMTP(host, int(os.getenv("WORKFLOW_SMTP_PORT", "587")), timeout=15) as client:
            client.starttls(context=ssl.create_default_context())
            client.login(os.environ["WORKFLOW_SMTP_USER"], os.environ["WORKFLOW_SMTP_PASSWORD"])
            client.send_message(message)
        return
    if kind in {"webhook", "webhook_queue"}:
        # Workflows cannot supply arbitrary target URLs. Administrators must configure
        # a single HTTPS endpoint outside the database; this eliminates URL-driven SSRF.
        target = os.getenv("WORKFLOW_WEBHOOK_URL", "").strip()
        url = urlparse(target)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
            raise ValueError("Set WORKFLOW_WEBHOOK_URL to a trusted HTTPS endpoint")
        payload = json.dumps({
            "event": "crm.workflow", "execution_id": execution.id,
            "resource": execution.resource, "record_id": execution.record_id,
            "organization_id": execution.organization_id, "value": action.get("value"),
        }, default=str).encode()
        import hashlib
        import hmac
        secret = os.getenv("WORKFLOW_WEBHOOK_SECRET", "")
        if len(secret) < 32:
            raise ValueError("WORKFLOW_WEBHOOK_SECRET must be at least 32 characters")
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        request = Request(target, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "X-CRM-Signature": "sha256=" + signature,
            "X-CRM-Idempotency-Key": execution.idempotency_key,
        })
        with build_opener(_NoRedirect()).open(request, timeout=12) as response:
            if not 200 <= response.status < 300:
                raise ValueError(f"Webhook delivery HTTP {response.status}")
        return
    raise ValueError("Unknown external workflow action")


def process_due(limit: int = 20, organization_id: int | None = None, *, report: bool = False, legacy_owner_id: int | None = None) -> int | dict:
    now = datetime.utcnow()
    processed = 0
    completed = 0
    failed = 0
    with SessionLocal() as db:
        # On PostgreSQL, row locking and SKIP LOCKED make the claim atomic.
        query = select(WorkflowExecution).where(
            or_(WorkflowExecution.status == "queued",
                (WorkflowExecution.status == "running") &
                (WorkflowExecution.locked_at < now - timedelta(seconds=LEASE_SECONDS))),
            or_(WorkflowExecution.scheduled_for.is_(None), WorkflowExecution.scheduled_for <= now),
            or_(WorkflowExecution.next_attempt_at.is_(None), WorkflowExecution.next_attempt_at <= now),
        ).order_by(WorkflowExecution.created_at).limit(min(limit, 50))
        if legacy_owner_id is not None:
            query = query.where(WorkflowExecution.organization_id.is_(None), WorkflowExecution.owner_id == legacy_owner_id)
        elif organization_id is not None:
            query = query.where(WorkflowExecution.organization_id == organization_id)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        candidates = db.scalars(query).all()
        ids = []
        for item in candidates:
            item.status = "running"
            item.locked_at = now
            item.attempts = (item.attempts or 0) + 1
            ids.append(item.id)
        db.commit()
    for execution_id in ids:
        with SessionLocal() as db:
            execution = db.get(WorkflowExecution, execution_id)
            if execution is None or execution.status != "running":
                continue
            org_token = TENANT_ORGANIZATION_ID.set(execution.organization_id)
            actor_token = TENANT_ACTOR_ID.set(execution.owner_id)
            try:
                rule = db.get(PlatformRecord, execution.rule_id)
                if rule is None or rule.archived or rule.status != "Active" or rule.organization_id != execution.organization_id:
                    raise ValueError("Workflow rule no longer belongs to this organization")
                if legacy_owner_id is not None and (execution.owner_id != legacy_owner_id or rule.owner_id != legacy_owner_id):
                    raise ValueError("Legacy workflow does not belong to the platform owner")
                model = RESOURCE_MAP.get(execution.resource)
                if model:
                    record = db.get(model, execution.record_id)
                else:
                    record = db.scalar(select(PlatformRecord).where(
                        PlatformRecord.id == execution.record_id,
                        PlatformRecord.resource == execution.resource))
                if record is None or getattr(record, "archived", False):
                    raise ValueError("Workflow source record is missing")
                if getattr(record, "organization_id", None) != execution.organization_id:
                    raise ValueError("Workflow source is outside the execution organization")
                if legacy_owner_id is not None and getattr(record, "owner_id", None) != legacy_owner_id:
                    raise ValueError("Legacy workflow source does not belong to the platform owner")
                values = (dict(record.data or {}) if isinstance(record, PlatformRecord)
                          else {column.name: getattr(record, column.name) for column in record.__table__.columns})
                for action in execution.actions or []:
                    kind = str(action.get("type") or "").lower()
                    if kind in {"email", "webhook", "webhook_queue", "deluge_http"}:
                        _send_external(action, execution)
                    else:
                        _execute_workflow_action(db, action, execution.resource, record, values)
                execution.status = "completed"
                execution.error = None
                execution.completed_at = datetime.utcnow()
                execution.locked_at = None
                add_audit(db, "automation", execution.resource, execution.record_id,
                          f"Background workflow execution #{execution.id} completed")
                db.commit()
                completed += 1
            except Exception as error:
                db.rollback()
                execution = db.get(WorkflowExecution, execution_id)
                if execution is not None:
                    execution.error = str(error)[:1000]
                    execution.locked_at = None
                    if execution.attempts >= MAX_ATTEMPTS:
                        execution.status = "failed"
                    else:
                        execution.status = "queued"
                        execution.next_attempt_at = datetime.utcnow() + timedelta(
                            seconds=min(3600, 30 * 2 ** (execution.attempts - 1)))
                    db.commit()
                failed += 1
                log.exception("Workflow delivery failed: execution=%s", execution_id)
            finally:
                TENANT_ACTOR_ID.reset(actor_token)
                TENANT_ORGANIZATION_ID.reset(org_token)
            processed += 1
    if report:
        return {"processed": processed, "completed": completed, "failed": failed, "skipped": 0, "run_at": now.isoformat()}
    return processed


def purge_recycle_bin(limit_per_module: int = 50) -> int:
    """Purge expired records by organization, without bypassing tenant scope."""
    from app.models import Organization
    from app.main import _purge_expired_recycle_records
    with SessionLocal() as db:
        org_ids = list(db.scalars(select(Organization.id)).all())
    removed = 0
    for org_id in org_ids:
        token = TENANT_ORGANIZATION_ID.set(org_id)
        try:
            with SessionLocal() as db:
                removed += _purge_expired_recycle_records(db, org_id)
                db.commit()
        finally:
            TENANT_ORGANIZATION_ID.reset(token)
    return removed


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    interval = max(5, min(300, int(os.getenv("WORKFLOW_POLL_SECONDS", "15"))))
    next_cleanup = 0.0
    while True:
        try:
            process_due()
        except Exception:
            log.exception("Workflow poll failed")
        if time.monotonic() >= next_cleanup:
            try:
                purge_recycle_bin()
            except Exception:
                log.exception("Recycle Bin cleanup failed")
            next_cleanup = time.monotonic() + 3600
        time.sleep(interval)


if __name__ == "__main__":
    main()
