from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import JSON as SAJSON, Boolean, Date, DateTime, Float, Integer, func, or_, select
from sqlalchemy.orm import Session

from app.database import TENANT_ACTOR_ID, TENANT_ORGANIZATION_ID
from app.models import *
from app.platform_catalog import PLATFORM_RESOURCES
from app.schemas import *


# Security is injected after the security service is loaded. This keeps the core
# record/automation layer independent from authentication implementation details.
_redact_hook = lambda db, resource, data, actor: data
_access_hook = lambda db, resource, record, actor, access="read": True
_org_resolver_hook = lambda db, user_id: None
_approval_create_hook = None

def configure_approval_hook(callback) -> None:
    global _approval_create_hook
    _approval_create_hook = callback

def configure_security_hooks(redact, access, organization_resolver) -> None:
    global _redact_hook, _access_hook, _org_resolver_hook
    _redact_hook = redact
    _access_hook = access
    _org_resolver_hook = organization_resolver

RESOURCE_MAP: dict[str, type[Base]] = {
    "leads": Lead,
    "contacts": Contact,
    "accounts": Account,
    "deals": Deal,
    "products": Product,
    "notes": Note,
    "attachments": Attachment,
    "emails": Email,
    "activities": Activity,
    "users": User,
    "approval_processes": ApprovalProcess,
    "blueprints": Blueprint,
}
SEARCH_COLUMNS: dict[str, list[str]] = {
    "leads": ["name", "company", "email", "source", "status"],
    "contacts": ["first_name", "last_name", "email", "job_title"],
    "accounts": ["name", "website", "industry", "billing_city"],
    "deals": ["name", "stage", "source", "status"],
    "products": ["name", "sku", "category", "status"],
    "notes": ["title", "content"],
    "attachments": ["name", "file_type"],
    "emails": ["subject", "from_email", "to_email", "status"],
    "activities": ["subject", "activity_type", "status", "related_type"],
    "users": ["name", "email", "role", "status"],
    "approval_processes": ["name", "module", "trigger", "approver", "status"],
    "blueprints": ["name", "module", "entry_criteria"],
}


def parse_date_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (date, datetime)):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_datetime_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))


def coerce_value(model: type[Base], key: str, value: Any) -> Any:
    column = model.__table__.columns.get(key)
    if column is None:
        return value
    if isinstance(column.type, DateTime):
        return parse_datetime_value(value)
    if isinstance(column.type, Date):
        return parse_date_value(value)
    if isinstance(column.type, Integer) and value not in (None, ""):
        return int(value)
    if isinstance(column.type, Float) and value not in (None, ""):
        return float(value)
    if isinstance(column.type, Boolean) and isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "on"}
    if isinstance(column.type, SAJSON) and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [part.strip() for part in value.split(",") if part.strip()]
    return value


def serialize(obj: Any, db: Session | None = None, actor: User | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in obj.__table__.columns:
        attribute = "metadata_json" if column.name == "metadata" and hasattr(obj, "metadata_json") else (column.key if hasattr(obj, column.key) else column.name)
        value = getattr(obj, attribute)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        data[column.name] = value
    if isinstance(obj, User):
        data.pop("password_hash", None)
        data.pop("password_changed_at", None)
    if isinstance(obj, AuthSession):
        data.pop("token_hash", None)
    if db is not None and hasattr(obj, "owner_id") and obj.owner_id:
        owner = db.get(User, obj.owner_id)
        data["owner_name"] = owner.name if owner else "Unassigned"
    if isinstance(obj, Contact):
        data["full_name"] = f"{obj.first_name} {obj.last_name}".strip()
    if isinstance(obj, Activity) and obj.related_type and obj.related_id:
        data["related_label"] = related_label(db, obj.related_type, obj.related_id) if db else None
    return _redact_hook(db, getattr(obj, "__tablename__", ""), data, actor) if db else data


def related_label(db: Session, related_type: str, related_id: int) -> str | None:
    model = RESOURCE_MAP.get(f"{related_type.lower()}s") or RESOURCE_MAP.get(related_type.lower())
    if model is None:
        return None
    item = db.get(model, related_id)
    if item is None:
        return None
    if isinstance(item, Contact):
        return f"{item.first_name} {item.last_name}".strip()
    return getattr(item, "name", getattr(item, "subject", f"{related_type} #{related_id}"))


def platform_config(resource: str) -> dict[str, Any]:
    config = PLATFORM_RESOURCES.get(resource)
    if config is None:
        raise HTTPException(404, "Unknown CONVOSIS CRM module or setup resource")
    return config


def platform_values(payload: PlatformPayload) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


def validate_platform_values(resource: str, values: dict[str, Any], *, partial: bool = False) -> None:
    config = platform_config(resource)
    field_map = {item["key"]: item for item in config.get("fields", [])}
    if not partial:
        for item in config.get("fields", []):
            if item.get("required") and values.get(item["key"]) in (None, "", []):
                raise HTTPException(422, f"{item['label']} is required")
    if resource == "workflow_rules":
        if values.get("event") == "field_change" and not str(values.get("trigger_field") or "").strip() and not partial:
            raise HTTPException(422, "Select a field for the field-change trigger")
        if values.get("scheduled_for"):
            try:
                datetime.fromisoformat(str(values["scheduled_for"]).replace("Z", "+00:00"))
            except (ValueError, TypeError) as error:
                raise HTTPException(422, "Schedule must be a valid ISO datetime") from error
    for key in values:
        if key not in field_map and key not in {"title", "owner_id", "account_id", "contact_id", "deal_id", "related_type", "related_id", "amount", "due_date", "status", "file_name", "file_size", "content_type", "storage_key", "paid_amount", "balance_due", "criteria", "actions", "scheduled_for"}:
            raise HTTPException(422, f"Unknown field '{key}' for {config['label']}")
    for item in config.get("fields", []):
        if item.get("type") == "json" and item["key"] in values and values[item["key"]] is not None and not isinstance(values[item["key"]], (dict, list)):
            raise HTTPException(422, f"{item['label']} must be valid JSON")
        if item.get("options") and values.get(item["key"]) not in (None, "") and str(values[item["key"]]) not in item["options"]:
            raise HTTPException(422, f"{item['label']} has an unsupported value")


def sync_platform_columns(record: PlatformRecord, values: dict[str, Any]) -> None:
    record.title = str(values.get("name") or values.get("title") or record.title or "Untitled").strip()
    record.status = str(values.get("status") or record.status or "Active")
    for key in ("owner_id", "account_id", "contact_id", "deal_id", "related_type", "related_id", "amount", "due_date"):
        if key in values:
            value = values[key]
            if key == "due_date" and isinstance(value, str) and value:
                value = date.fromisoformat(value[:10])
            setattr(record, key, value)
    record.data = json_safe(values)


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def get_platform_reference(db: Session, resource: str, raw_id: Any, label: str) -> PlatformRecord:
    try:
        item_id = int(raw_id)
    except (TypeError, ValueError) as error:
        raise HTTPException(422, f"Select a valid {label.lower()}") from error
    record = db.scalar(select(PlatformRecord).where(
        PlatformRecord.resource == resource,
        PlatformRecord.id == item_id,
        PlatformRecord.archived == False,
    ))
    if record is None:
        raise HTTPException(422, f"The selected {label.lower()} no longer exists")
    return record


def normalize_platform_links(db: Session, resource: str, values: dict[str, Any]) -> None:
    """Validate cross-module links and inherit shared customer/revenue context."""
    parent: PlatformRecord | None = None
    if resource == "quotes" and values.get("deal_id"):
        deal = db.get(Deal, int(values["deal_id"]))
        if deal is None or deal.archived:
            raise HTTPException(422, "The selected opportunity no longer exists")
        if values.get("account_id") in (None, ""):
            values["account_id"] = deal.account_id
        if values.get("contact_id") in (None, ""):
            values["contact_id"] = deal.contact_id
        if values.get("owner_id") in (None, ""):
            values["owner_id"] = deal.owner_id
        if values.get("amount") in (None, ""):
            values["amount"] = deal.amount
        values.update({"related_type": "deals", "related_id": deal.id})
    elif resource == "sales_orders" and values.get("quote_id"):
        parent = get_platform_reference(db, "quotes", values["quote_id"], "Quote")
    elif resource == "purchase_orders" and values.get("vendor_id"):
        parent = get_platform_reference(db, "vendors", values["vendor_id"], "Vendor")
    elif resource == "invoices" and values.get("sales_order_id"):
        parent = get_platform_reference(db, "sales_orders", values["sales_order_id"], "Sales order")
    elif resource == "payments" and values.get("invoice_id"):
        parent = get_platform_reference(db, "invoices", values["invoice_id"], "Invoice")
    elif resource == "site_visits" and values.get("lead_id"):
        lead = db.get(Lead, int(values["lead_id"]))
        if lead is None or lead.archived:
            raise HTTPException(422, "The selected lead no longer exists")
        if values.get("owner_id") in (None, ""):
            values["owner_id"] = lead.owner_id
        values.update({"related_type": "leads", "related_id": lead.id})

    if parent is not None:
        inherited = _platform_data_dict(parent)
        for key in ("owner_id", "account_id", "contact_id", "deal_id"):
            if values.get(key) in (None, "") and getattr(parent, key, None) is not None:
                values[key] = getattr(parent, key)
        if values.get("amount") in (None, "") and parent.amount is not None:
            values["amount"] = parent.amount
        values.update({"related_type": parent.resource, "related_id": parent.id})


TRANSACTION_NUMBERS = {
    "quotes": ("quote_number", "QUO"),
    "sales_orders": ("order_number", "SO"),
    "purchase_orders": ("po_number", "PO"),
    "invoices": ("invoice_number", "INV"),
}


def ensure_transaction_number(record: PlatformRecord) -> None:
    definition = TRANSACTION_NUMBERS.get(record.resource)
    if not definition:
        return
    key, prefix = definition
    values = _platform_data_dict(record)
    if not values.get(key):
        values[key] = f"{prefix}-{datetime.utcnow():%Y%m}-{record.id:05d}"
        sync_platform_columns(record, values)


def refresh_invoice_balance(db: Session, invoice_id: int) -> None:
    invoice = db.scalar(select(PlatformRecord).where(
        PlatformRecord.resource == "invoices", PlatformRecord.id == invoice_id,
        PlatformRecord.archived == False,
    ))
    if invoice is None:
        return
    payments = db.scalars(select(PlatformRecord).where(
        PlatformRecord.resource == "payments", PlatformRecord.archived == False,
    )).all()
    paid = sum(
        float(item.amount or 0)
        for item in payments
        if int(_platform_data_dict(item).get("invoice_id") or 0) == invoice_id
        and item.status in {"Received", "Cleared"}
    )
    total = float(invoice.amount or 0)
    values = _platform_data_dict(invoice)
    values["paid_amount"] = paid
    values["balance_due"] = max(total - paid, 0)
    if paid >= total and total > 0:
        values["status"] = "Paid"
    elif paid > 0:
        values["status"] = "Partially Paid"
    sync_platform_columns(invoice, values)


def _platform_data_dict(record: PlatformRecord) -> dict[str, Any]:
    """Return a safe mutable mapping for current and legacy PlatformRecord JSON.

    Older deployments may contain null, list, or scalar JSON values from historical
    imports/customization code. A malformed legacy value must never turn a module
    list page into HTTP 500; canonical fields below remain authoritative.
    """
    raw = record.data
    return dict(raw) if isinstance(raw, dict) else {}


def serialize_platform(record: PlatformRecord, db: Session | None = None, actor: User | None = None) -> dict[str, Any]:
    data = _platform_data_dict(record)
    data.update({
        "id": record.id,
        "resource": record.resource,
        "name": record.title,
        "title": record.title,
        "status": record.status,
        "owner_id": record.owner_id,
        "account_id": record.account_id,
        "contact_id": record.contact_id,
        "deal_id": record.deal_id,
        "related_type": record.related_type,
        "related_id": record.related_id,
        "amount": record.amount,
        "due_date": record.due_date.isoformat() if record.due_date else None,
        "archived": record.archived,
        "version": record.version,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    })
    if db and record.owner_id:
        owner = db.get(User, record.owner_id)
        data["owner_name"] = owner.name if owner else None
    return _redact_hook(db, record.resource, data, actor) if db else data


def add_audit(db: Session, action: str, resource: str, record_id: int | None,
              summary: str, before: dict[str, Any] | None = None,
              after: dict[str, Any] | None = None, actor_id: int | None = None) -> None:
    organization_id = TENANT_ORGANIZATION_ID.get()
    if organization_id is None and actor_id:
        organization_id = _org_resolver_hook(db, actor_id)
    db.add(AuditEvent(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource=resource,
        record_id=record_id,
        summary=summary[:300],
        before=before,
        after=after,
    ))


def _workflow_value(values: dict[str, Any], field: str) -> Any:
    return values.get(field)


def _workflow_condition(values: dict[str, Any], condition: dict[str, Any]) -> bool:
    field = str(condition.get("field") or "")
    operator = str(condition.get("operator") or "equals").lower()
    actual = _workflow_value(values, field)
    expected = condition.get("value")
    if operator in {"is_empty", "empty"}:
        return actual in (None, "", [])
    if operator in {"is_not_empty", "not_empty"}:
        return actual not in (None, "", [])
    if operator in {"contains", "includes"}:
        return str(expected).lower() in str(actual or "").lower()
    if operator in {"does_not_contain", "not_contains"}:
        return str(expected).lower() not in str(actual or "").lower()
    if operator in {"starts_with", "starts"}:
        return str(actual or "").lower().startswith(str(expected or "").lower())
    if operator in {"ends_with", "ends"}:
        return str(actual or "").lower().endswith(str(expected or "").lower())
    if operator in {"in", "one_of"}:
        return str(actual) in {str(item) for item in (expected if isinstance(expected, list) else str(expected).split(","))}
    if operator in {"greater_than", ">"}:
        try:
            return float(actual) > float(expected)
        except (TypeError, ValueError):
            return False
    if operator in {"less_than", "<"}:
        try:
            return float(actual) < float(expected)
        except (TypeError, ValueError):
            return False
    if operator in {"not_equals", "does_not_equal"}:
        return str(actual) != str(expected)
    return str(actual) == str(expected)


def workflow_criteria_match(values: dict[str, Any], criteria: Any) -> bool:
    """Evaluate nested AND/OR criteria while retaining legacy single-field rules."""
    if not criteria:
        return True
    if isinstance(criteria, dict):
        if "conditions" in criteria:
            conditions = criteria.get("conditions") or []
            results = [workflow_criteria_match(values, item) for item in conditions]
            return all(results) if str(criteria.get("logic", "AND")).upper() != "OR" else any(results)
        return _workflow_condition(values, criteria)
    if isinstance(criteria, list):
        criteria = {"logic": "AND", "conditions": criteria}
    if not isinstance(criteria, dict):
        return False
    conditions = criteria.get("conditions") or []
    results = [workflow_criteria_match(values, item) for item in conditions]
    return all(results) if str(criteria.get("logic", "AND")).upper() != "OR" else any(results)


def _workflow_actions(config: dict[str, Any]) -> list[dict[str, Any]]:
    actions = config.get("actions")
    if isinstance(actions, list) and actions:
        return [item if isinstance(item, dict) else {"type": str(item)} for item in actions]
    action_type = config.get("action_type") or "audit"
    return [{"type": action_type, "value": config.get("action_value")}]


def _record_title(record: Any) -> str:
    if isinstance(record, PlatformRecord):
        return record.title
    if isinstance(record, Contact):
        return f"{record.first_name} {record.last_name}".strip() or f"Contact #{record.id}"
    return str(getattr(record, "name", None) or getattr(record, "subject", None) or getattr(record, "title", None) or f"Record #{getattr(record, 'id', '?')}")


def _execute_workflow_action(db: Session, action: dict[str, Any], resource: str, record: Any, values: dict[str, Any]) -> None:
    action_type = str(action.get("type") or action.get("action_type") or "audit").lower()
    value = action.get("value", action.get("action_value"))
    title = _record_title(record)
    def validate_target_member(user_id: int) -> int:
        org_id = getattr(record, "organization_id", None) or TENANT_ORGANIZATION_ID.get()
        user = db.get(User, user_id)
        if user is None or user.status != "Active":
            raise ValueError("Workflow target user must be active")
        if org_id is not None:
            member = db.scalar(select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "Active",
            ))
            if member is None:
                raise ValueError("Workflow target user is not an active member of this organization")
        return user_id
    if action_type in {"field_update", "update_field"}:
        field_name = str(action.get("field") or "").strip()
        field_value = action.get("value")
        if not field_name and value and "=" in str(value):
            field_name, field_value = str(value).split("=", 1)
        field_name = field_name.strip()
        if not field_name:
            raise ValueError("field_update requires a field")
        if field_name.lower() in {"id", "organization_id", "owner_id", "password", "password_hash", "created_at", "updated_at", "version", "is_platform_owner", "membership_role"}:
            raise ValueError("Workflow actions cannot change system-managed or tenant identity fields")
        if isinstance(record, PlatformRecord):
            changed = dict(record.data or {})
            changed[field_name] = field_value
            sync_platform_columns(record, changed)
        else:
            column = record.__table__.columns.get(field_name)
            if column is None:
                raise ValueError(f"Unknown field '{field_name}' for {resource}")
            setattr(record, field_name, coerce_value(type(record), field_name, field_value))
    elif action_type in {"create_task", "task"}:
        owner_id = getattr(record, "owner_id", None)
        db.add(Activity(activity_type="Task", subject=str(value or action.get("subject") or f"Follow up: {title}"), owner_id=owner_id, status="Open", priority=str(action.get("priority") or "Normal"), related_type=resource, related_id=record.id))
    elif action_type in {"notification", "notify"}:
        fallback_owner = getattr(record, "owner_id", None)
        user_id = validate_target_member(int(action.get("user_id") or fallback_owner))
        db.add(Notification(user_id=user_id, kind=str(action.get("kind") or "workflow"), title=str(action.get("title") or f"Workflow update: {title}"), body=str(value or action.get("body") or "A workflow action was triggered."), resource=resource, record_id=record.id))
    elif action_type in {"owner_change", "assign_owner"}:
        if not hasattr(record, "owner_id"):
            raise ValueError(f"{resource} does not support ownership")
        record.owner_id = validate_target_member(int(action.get("user_id") or value))
    elif action_type in {"start_approval", "approval"}:
        process_id = int(action.get("process_id") or value or 0)
        process = db.get(ApprovalProcess, process_id)
        if process is None:
            raise ValueError("start_approval requires a valid process_id")
        if _approval_create_hook is None:
            raise RuntimeError("Approval service is not registered")
        request, duplicate = _approval_create_hook(process, resource, record.id, getattr(record, "owner_id", None), action.get("comment"), db)
        if duplicate:
            add_audit(db, "approval_duplicate", resource, record.id, f"Approval request already exists for process '{process.name}'")
    elif action_type == "tag":
        if isinstance(record, PlatformRecord):
            changed = dict(record.data or {})
            tags = list(changed.get("tags") or [])
            if value and str(value) not in tags:
                tags.append(str(value))
            changed["tags"] = tags
            sync_platform_columns(record, changed)
        elif hasattr(record, "tags"):
            tags = list(getattr(record, "tags") or [])
            if value and str(value) not in tags:
                tags.append(str(value))
            record.tags = tags
        else:
            raise ValueError(f"{resource} does not support tags")
    elif action_type == "function":
        # Functions are declarative, tenant-scoped CRM action sequences; never eval user code.
        identifier = action.get("function_id") or value
        try:
            function_id = int(identifier)
        except (ValueError, TypeError):
            raise ValueError("Function action requires a valid function ID")
        function_record = db.scalar(select(PlatformRecord).where(
            PlatformRecord.id == function_id,
            PlatformRecord.resource == "functions",
            PlatformRecord.archived == False,
            PlatformRecord.status == "Active",
        ))
        if function_record is None:
            raise ValueError("Active custom function not found in this organization")
        spec = (function_record.data or {}).get("source")
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except json.JSONDecodeError as error:
                raise ValueError("Custom function source must contain valid JSON") from error
        if isinstance(spec, dict):
            if str((function_record.data or {}).get("runtime", "")).lower() == "deluge":
                from app.deluge_subset import parse_deluge
                try:
                    spec = parse_deluge(spec.get("code"))
                except HTTPException:
                    from app.deluge_program import compile_deluge_program
                    spec = [{"type": "deluge_program", "program": compile_deluge_program(spec.get("code"))}]
            else:
                spec = spec.get("steps")
        if not isinstance(spec, list) or not 1 <= len(spec) <= 20:
            raise ValueError("Custom function must have 1 to 20 action steps")
        allowed = {"field_update", "update_field", "create_task", "task", "notification", "notify", "tag", "audit", "webhook_queue", "crm_update_current", "variable_assign", "return", "deluge_program"}
        local_vars = {}
        def resolve(template):
            if isinstance(template, dict) and set(template) == {"$deluge_expr"}:
                from app.deluge_expressions import evaluate_deluge_expression
                context = {**dict(getattr(record, "data", None) or {}), **values}
                try:
                    return evaluate_deluge_expression(template["$deluge_expr"], context, local_vars)
                except HTTPException as exc:
                    raise ValueError("Deluge expression rejected") from exc
            if isinstance(template, str) and template.startswith("$record."):
                field = template[8:]
                if not field or field.startswith("_") or "." in field:
                    raise ValueError("Invalid function record field")
                if field in {"password", "password_hash", "organization_id"}:
                    raise ValueError("Protected function record field")
                return values.get(field, getattr(record, field, None))
            return template
        def run_resolved_step(resolved_step):
                if str(resolved_step.get("type", "")).lower() == "return":
                    return "return"
                elif str(resolved_step.get("type", "")).lower() == "variable_assign":
                    name = str(resolved_step.get("name", ""))
                    if not name.isidentifier() or name.startswith("_") or name in {"record", "crm"}:
                        raise ValueError("Invalid Deluge variable name")
                    if len(local_vars) >= 40 and name not in local_vars:
                        raise ValueError("Deluge variable limit exceeded")
                    local_vars[name] = resolved_step.get("value")
                elif str(resolved_step.get("type", "")).lower() == "crm_update_current":
                    module = str(resolved_step.get("module") or "").lower().replace(" ", "_")
                    if module != resource.lower().replace(" ", "_"):
                        raise ValueError("CRM integration task must target the current module")
                    fields = resolved_step.get("fields")
                    if not isinstance(fields, dict) or not 1 <= len(fields) <= 10:
                        raise ValueError("Invalid CRM update field map")
                    for field, value in fields.items():
                        _execute_workflow_action(db, {"type": "field_update", "field": field, "value": value}, resource, record, values)
                elif str(resolved_step.get("type", "")).lower() == "webhook_queue":
                    from uuid import uuid4
                    # Only the separate worker performs external I/O. The destination
                    # is exclusively WORKFLOW_WEBHOOK_URL, not script-controlled.
                    db.add(WorkflowExecution(
                        organization_id=getattr(record, "organization_id", None) or function_record.organization_id,
                        owner_id=getattr(record, "owner_id", None) or function_record.owner_id,
                        rule_id=function_record.id,
                        resource=resource,
                        record_id=record.id,
                        event="deluge_outbound",
                        status="queued",
                        actions=[resolved_step],
                        idempotency_key="deluge|" + uuid4().hex,
                    ))
                else:
                    _execute_workflow_action(db, resolved_step, resource, record, values)

        def handle_program_action(step, variables):
            local_vars.clear()
            local_vars.update(variables)
            resolved_step = {key: resolve(value) for key, value in step.items() if key != "_conditions"}
            run_resolved_step(resolved_step)
        for step in spec:
            if isinstance(step, dict) and step.get("type") == "deluge_program":
                from app.deluge_program import execute_deluge_program
                context = {**dict(getattr(record, "data", None) or {}), **values}
                execute_deluge_program(step["program"], context, handle_program_action)
                continue
            if not isinstance(step, dict) or str(step.get("type", "")).lower() not in allowed:
                raise ValueError("Unsupported custom function step")
            conditions = step.get("_conditions", [])
            if conditions:
                if not isinstance(conditions, list) or len(conditions) > 5:
                    raise ValueError("Invalid function condition")
                matched = True
                for condition in conditions:
                    if isinstance(condition, dict) and "expression" in condition:
                        from app.deluge_expressions import evaluate_deluge_expression
                        context = {**dict(getattr(record, "data", None) or {}), **values}
                        try:
                            result = evaluate_deluge_expression(condition["expression"], context, local_vars)
                        except HTTPException as exc:
                            raise ValueError("Deluge condition rejected") from exc
                        if result is not True:
                            matched = False
                            break
                        continue
                    field = condition.get("field", "")
                    if not isinstance(field, str) or not field.isidentifier() or field.startswith("_") or field.lower() in {"password", "password_hash", "organization_id", "id", "owner_id", "created_by"}:
                        raise ValueError("Invalid function condition field")
                    actual = values.get(field, getattr(record, field, None))
                    expected = condition.get("value")
                    operator = condition.get("operator")
                    if operator not in {"==", "!="}:
                        raise ValueError("Invalid function condition operator")
                    if (str(actual) == str(expected)) != (operator == "=="):
                        matched = False
                        break
                if not matched:
                    continue
            resolved_step = {key: resolve(item) for key, item in step.items() if key != "_conditions"}
            if run_resolved_step(resolved_step) == "return":
                break
        add_audit(db, "function_executed", resource, record.id, f"Custom function '{function_record.title}' executed")
    elif action_type in {"webhook", "webhook_queue", "email", "call", "meeting"}:
        add_audit(db, "automation_queued", resource, record.id, f"Queued workflow action '{action_type}' for external worker")
    elif action_type != "audit":
        raise ValueError(f"Unsupported workflow action '{action_type}'")


def run_record_automation(db: Session, resource: str, event: str, record: Any, values: dict[str, Any], before_values: dict[str, Any] | None = None) -> None:
    """Run CRM workflow rules for both core SQLAlchemy records and generic platform records."""
    rules = db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "workflow_rules", PlatformRecord.archived == False, PlatformRecord.status == "Active").order_by(PlatformRecord.id)).all()
    normalized_resource = resource.lower().replace(" ", "_")
    aliases = {normalized_resource, normalized_resource.rstrip("s")}
    for rule in rules:
        config = rule.data or {}
        configured = str(config.get("module", "")).lower().replace(" ", "_")
        if configured not in aliases | {"all", "*"}:
            continue
        trigger = str(config.get("event") or "create_or_edit").lower()
        allowed_events = {"create", "create_or_edit", "edit", "update", "field_change"}
        if trigger not in allowed_events:
            continue
        if trigger == "field_change":
            watched = str(config.get("trigger_field") or "").strip()
            if event != "update" or not watched or before_values is None:
                continue
            if watched not in values or before_values.get(watched) == values.get(watched):
                continue
        elif trigger != "create_or_edit" and not (trigger == event or (trigger == "edit" and event == "update")):
            continue
        criteria = config.get("criteria") or ({"field": config.get("criteria_field"), "operator": "equals", "value": config.get("criteria_value")} if config.get("criteria_field") else None)
        criteria_values = {**(before_values or {}), **values}
        if not workflow_criteria_match(criteria_values, criteria):
            continue
        actions = _workflow_actions(config)
        state_token = getattr(record, "version", None) or getattr(record, "updated_at", None) or getattr(record, "created_at", None) or json.dumps(criteria_values, sort_keys=True, default=str)
        key = f"{rule.id}|{resource}|{record.id}|{event}|{state_token}|{json.dumps(actions, sort_keys=True, default=str)}"
        if db.scalar(select(WorkflowExecution).where(WorkflowExecution.idempotency_key == key)):
            continue
        scheduled_for = None
        if config.get("scheduled_for"):
            try:
                scheduled_for = datetime.fromisoformat(str(config["scheduled_for"]).replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                scheduled_for = None
        external = any(str(item.get("type", "")).lower() in {"email", "webhook", "webhook_queue"} for item in actions)
        execution = WorkflowExecution(organization_id=getattr(record, "organization_id", None) or rule.organization_id or TENANT_ORGANIZATION_ID.get(), owner_id=record.owner_id, rule_id=rule.id, resource=resource, record_id=record.id, event=event, status="queued" if scheduled_for or external else "running", actions=actions, scheduled_for=scheduled_for, idempotency_key=key)
        db.add(execution)
        db.flush()
        if scheduled_for or external:
            add_audit(db, "automation_scheduled", resource, record.id, f"Workflow '{rule.title}' scheduled {len(actions)} action(s)")
            continue
        try:
            for action in actions:
                _execute_workflow_action(db, action, resource, record, values)
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            add_audit(db, "automation", resource, record.id, f"Workflow '{rule.title}' executed {len(actions)} action(s)")
        except (ValueError, TypeError) as error:
            execution.status = "failed"
            execution.error = str(error)
            add_audit(db, "automation_error", resource, record.id, f"Workflow '{rule.title}' failed: {error}")


def run_platform_automation(db: Session, resource: str, event: str, record: PlatformRecord, values: dict[str, Any], before_values: dict[str, Any] | None = None) -> None:
    run_record_automation(db, resource, event, record, values, before_values)

def _active_blueprint(db: Session, resource: str) -> Blueprint | None:
    aliases = {resource.lower(), resource.rstrip("s").lower(), resource.replace("_", " ").lower(), resource.rstrip("s").replace("_", " ").lower()}
    blueprints = db.scalars(select(Blueprint).where(Blueprint.active == True, Blueprint.archived == False).order_by(Blueprint.id)).all()
    return next((item for item in blueprints if str(item.module or "").lower() in aliases or str(item.module or "").lower().replace(" ", "_") in aliases), None)


def enforce_blueprint_transition(db: Session, resource: str, record: Any, from_stage: str | None, to_stage: str | None, values: dict[str, Any]) -> Blueprint | None:
    if not from_stage or not to_stage or from_stage == to_stage:
        return None
    blueprint = _active_blueprint(db, resource)
    if blueprint is None:
        return None
    transitions = blueprint.transitions or []
    matching = next((item for item in transitions if str(item.get("from")) == str(from_stage) and str(item.get("to")) == str(to_stage)), None)
    if transitions and matching is None:
        raise HTTPException(422, detail={"code": "BLUEPRINT_TRANSITION_NOT_ALLOWED", "message": f"Blueprint '{blueprint.name}' does not allow {from_stage} → {to_stage}.", "from": from_stage, "to": to_stage})
    requirements = (matching or {}).get("required") or next((item.get("required", []) for item in (blueprint.transition_requirements or []) if str(item.get("transition") or "") in {f"{from_stage} -> {to_stage}", str(to_stage)}), [])
    missing = [str(field) for field in requirements if values.get(str(field)) in (None, "", [])]
    if missing:
        raise HTTPException(422, detail={"code": "BLUEPRINT_REQUIREMENTS_MISSING", "message": "Complete the required fields before this transition.", "missing": missing, "from": from_stage, "to": to_stage})
    return blueprint


def record_blueprint_transition(db: Session, blueprint: Blueprint | None, resource: str, record_id: int, from_stage: str, to_stage: str, values: dict[str, Any], actor_id: int | None = None) -> None:
    if blueprint is None or from_stage == to_stage:
        return
    matching = next((item for item in (blueprint.transitions or []) if str(item.get("from")) == str(from_stage) and str(item.get("to")) == str(to_stage)), {})
    requirements = matching.get("required") or []
    db.add(BlueprintTransitionLog(blueprint_id=blueprint.id, module=resource, record_id=record_id, from_stage=from_stage, to_stage=to_stage, actor_id=actor_id, requirements=requirements))
    add_audit(db, "blueprint_transition", resource, record_id, f"Blueprint '{blueprint.name}' moved {from_stage} → {to_stage}", before={"stage": from_stage}, after={"stage": to_stage}, actor_id=actor_id)


def apply_assignment_rule(db: Session, resource: str, values: dict[str, Any]) -> None:
    if values.get("owner_id"):
        return
    rules = db.scalars(select(PlatformRecord).where(
        PlatformRecord.resource == "assignment_rules", PlatformRecord.archived == False,
        PlatformRecord.status == "Active"
    ).order_by(PlatformRecord.id)).all()
    for rule in rules:
        config = rule.data or {}
        if str(config.get("module", "")).lower().replace(" ", "_") != resource:
            continue
        criterion = config.get("criteria_field")
        if criterion and str(values.get(criterion, "")) != str(config.get("criteria_value", "")):
            continue
        if config.get("owner_id"):
            values["owner_id"] = int(config["owner_id"])
            return


def seed_defaults(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    now = datetime.utcnow()
    maya = User(name="Maya Iyer", email="maya@yashcrm.app", role="Administrator", status="Active", last_active=now)
    arjun = User(name="Arjun Mehta", email="arjun@yashcrm.app", role="Sales manager", status="Active", last_active=now - timedelta(hours=2))
    riya = User(name="Riya Shah", email="riya@yashcrm.app", role="Sales rep", status="Active", last_active=now - timedelta(days=1))
    db.add_all([maya, arjun, riya])
    db.flush()

    acme = Account(name="Acme Retail Group", website="acmeretail.example", phone="+91 80 4000 1222", industry="Retail", employees=420, annual_revenue=28500000, type="Customer", owner_id=arjun.id, billing_city="Bengaluru", billing_country="India", notes="Regional retail group expanding into two new cities.", tags=["priority", "expansion"])
    northstar = Account(name="Northstar Logistics", website="northstar.example", phone="+91 22 4200 9911", industry="Logistics", employees=180, annual_revenue=14200000, type="Prospect", owner_id=riya.id, billing_city="Mumbai", billing_country="India", notes="Evaluating a unified customer operations workspace.", tags=["new"])
    evergreen = Account(name="Evergreen Labs", website="evergreen.example", phone="+91 11 4800 2144", industry="Technology", employees=75, annual_revenue=6900000, type="Partner", owner_id=maya.id, billing_city="New Delhi", billing_country="India", notes="Technology partner for integration opportunities.", tags=["partner"])
    db.add_all([acme, northstar, evergreen])
    db.flush()

    leads = [
        Lead(name="Nikhil Rao", company="Orbit Foods", email="nikhil@orbitfoods.example", phone="+91 98 2200 7711", source="Website", status="Qualified", owner_id=arjun.id, lead_score=82, next_follow_up=date.today() + timedelta(days=2), notes="Strong fit for multi-location rollout.", tags=["hot", "retail"]),
        Lead(name="Sara Thomas", company="Fieldstone Design", email="sara@fieldstone.example", phone="+91 99 1002 1981", source="Referral", status="Contacted", owner_id=riya.id, lead_score=58, next_follow_up=date.today() + timedelta(days=5), notes="Requested a short overview and pricing range.", tags=["design"]),
        Lead(name="Dev Malhotra", company="Kite Health", email="dev@kitehealth.example", phone="+91 97 4400 8812", source="LinkedIn", status="New", owner_id=maya.id, lead_score=41, next_follow_up=date.today() + timedelta(days=1), notes="New inbound lead.", tags=["inbound"]),
        Lead(name="Aanya Kapoor", company="Urban Nest", email="aanya@urbannest.example", phone="+91 98 7112 4400", source="Event", status="Converted", owner_id=arjun.id, lead_score=91, next_follow_up=None, notes="Converted after product workshop.", tags=["converted"]),
    ]
    db.add_all(leads)
    db.flush()

    contacts = [
        Contact(first_name="Priya", last_name="Nair", email="priya@acmeretail.example", phone="+91 98 6011 2244", job_title="Head of Operations", department="Operations", account_id=acme.id, owner_id=arjun.id, notes="Primary business sponsor.", tags=["champion"]),
        Contact(first_name="Kabir", last_name="Joshi", email="kabir@northstar.example", phone="+91 98 2012 4411", job_title="VP Customer Experience", department="Customer Experience", account_id=northstar.id, owner_id=riya.id, notes="Owns the evaluation committee.", tags=["evaluation"]),
        Contact(first_name="Meera", last_name="Sethi", email="meera@evergreen.example", phone="+91 99 2100 1893", job_title="Partnerships Lead", department="Partnerships", account_id=evergreen.id, owner_id=maya.id, notes="Integration partner contact.", tags=["partner"]),
    ]
    db.add_all(contacts)
    db.flush()

    deals = [
        Deal(name="Acme CX rollout", account_id=acme.id, contact_id=contacts[0].id, amount=480000, stage="Proposal", probability=60, expected_close_date=date.today() + timedelta(days=24), owner_id=arjun.id, type="New business", source="Website", status="Open", notes="Proposal review scheduled next week."),
        Deal(name="Northstar service desk", account_id=northstar.id, contact_id=contacts[1].id, amount=275000, stage="Needs Analysis", probability=35, expected_close_date=date.today() + timedelta(days=48), owner_id=riya.id, type="New business", source="Referral", status="Open", notes="Discovery workshop in progress."),
        Deal(name="Evergreen integration", account_id=evergreen.id, contact_id=contacts[2].id, amount=125000, stage="Negotiation", probability=78, expected_close_date=date.today() + timedelta(days=11), owner_id=maya.id, type="Partnership", source="Partner", status="Open", notes="Commercial terms under review."),
        Deal(name="Urban Nest pilot", account_id=acme.id, contact_id=contacts[0].id, amount=95000, stage="Closed Won", probability=100, expected_close_date=date.today() - timedelta(days=4), owner_id=arjun.id, type="Expansion", source="Event", status="Won", notes="Pilot converted to annual contract."),
    ]
    db.add_all(deals)
    db.flush()

    activities = [
        Activity(activity_type="Meeting", subject="Proposal review with Acme", due_at=datetime.utcnow() + timedelta(days=2, hours=3), owner_id=arjun.id, status="Open", priority="High", related_type="accounts", related_id=acme.id, description="Review the proposal and implementation timeline."),
        Activity(activity_type="Call", subject="Discovery follow-up with Northstar", due_at=datetime.utcnow() + timedelta(days=1, hours=2), owner_id=riya.id, status="Open", priority="Normal", related_type="deals", related_id=deals[1].id, description="Confirm decision criteria and stakeholders."),
        Activity(activity_type="Task", subject="Send integration checklist", due_at=datetime.utcnow() - timedelta(hours=4), owner_id=maya.id, status="Open", priority="High", related_type="contacts", related_id=contacts[2].id, description="Share the current API checklist."),
        Activity(activity_type="Call", subject="Welcome call completed", due_at=datetime.utcnow() - timedelta(days=1), owner_id=arjun.id, status="Completed", priority="Normal", related_type="leads", related_id=leads[3].id, description="Introductory call completed.", completed_at=datetime.utcnow() - timedelta(days=1)),
    ]
    db.add_all(activities)
    db.add(OrganizationSetting(id=1, org_name="CONVOSIS CRM", timezone="Asia/Kolkata", currency="INR", date_format="DD MMM YYYY", fiscal_year_start="April", default_pipeline="Default sales pipeline", notifications={"daily_digest": True, "mentions": True, "deal_updates": True}))
    db.add(ApprovalProcess(name="Discount approval", module="Deals", trigger="Discount is greater than 15%", approver="Sales manager", status="Active", conditions=[{"field": "discount", "operator": ">", "value": "15"}], steps=[{"order": 1, "approver": "Sales manager"}]))
    db.add(Blueprint(name="Deal progression", module="Deals", entry_criteria="Amount is greater than 0", stages=[{"id": "qualification", "label": "Qualification"}, {"id": "needs-analysis", "label": "Needs Analysis"}, {"id": "proposal", "label": "Proposal"}, {"id": "negotiation", "label": "Negotiation"}, {"id": "closed-won", "label": "Closed Won"}], transitions=[{"from": "Qualification", "to": "Needs Analysis", "label": "Qualify"}, {"from": "Needs Analysis", "to": "Proposal", "label": "Create proposal"}, {"from": "Proposal", "to": "Negotiation", "label": "Start negotiation"}, {"from": "Negotiation", "to": "Closed Won", "label": "Close won"}], active=True))
    db.commit()


def ensure_workspace_defaults(db: Session) -> None:
    """Provision baseline settings/security records inside the active tenant."""
    organization_id = TENANT_ORGANIZATION_ID.get()
    actor_id = TENANT_ACTOR_ID.get()

    settings_query = select(OrganizationSetting)
    if organization_id is None:
        settings_query = settings_query.where(OrganizationSetting.organization_id.is_(None))
    else:
        settings_query = settings_query.where(OrganizationSetting.organization_id == organization_id)
    setting = db.scalar(settings_query.order_by(OrganizationSetting.id))
    if setting is None:
        db.add(OrganizationSetting(
            owner_id=actor_id,
            organization_id=organization_id,
            org_name="CONVOSIS CRM",
            timezone="Asia/Kolkata",
            currency="INR",
            date_format="DD MMM YYYY",
            fiscal_year_start="April",
            default_pipeline="Default sales pipeline",
            notifications={"daily_digest": True, "mentions": True, "deal_updates": True},
        ))

    approval_query = select(ApprovalProcess.id)
    blueprint_query = select(Blueprint.id)
    sharing_query = select(SharingPolicy.id)
    if organization_id is None:
        approval_query = approval_query.where(ApprovalProcess.organization_id.is_(None))
        blueprint_query = blueprint_query.where(Blueprint.organization_id.is_(None))
    else:
        approval_query = approval_query.where(ApprovalProcess.organization_id == organization_id)
        blueprint_query = blueprint_query.where(Blueprint.organization_id == organization_id)

    if db.scalar(approval_query.limit(1)) is None:
        db.add(ApprovalProcess(
            organization_id=organization_id,
            name="Discount approval",
            module="Deals",
            trigger="Discount is greater than 15%",
            approver="Sales manager",
            status="Active",
            conditions=[{"field": "discount", "operator": ">", "value": "15"}],
            steps=[{"order": 1, "approver": "Sales manager"}],
        ))
    if db.scalar(blueprint_query.limit(1)) is None:
        db.add(Blueprint(
            organization_id=organization_id,
            name="Deal progression",
            module="Deals",
            entry_criteria="Amount is greater than 0",
            stages=[{"id": "qualification", "label": "Qualification"}],
            transitions=[],
            transition_requirements=[],
            active=True,
        ))

    default_sharing = [
        ("Core role hierarchy", "*", "role_hierarchy", "Read Only"),
        ("Products are publicly readable", "products", "Public Read Only", "Read Only"),
    ]
    for name, module, scope, access in default_sharing:
        policy_query = select(SharingPolicy.id).where(SharingPolicy.name == name)
        if organization_id is None:
            policy_query = policy_query.where(SharingPolicy.organization_id.is_(None))
        else:
            policy_query = policy_query.where(SharingPolicy.organization_id == organization_id)
        if db.scalar(policy_query) is None:
            db.add(SharingPolicy(
                organization_id=organization_id,
                name=name,
                module=module,
                scope=scope,
                criteria={},
                access=access,
                enabled=True,
            ))

    owner = db.get(User, actor_id) if actor_id else None
    if owner is None and organization_id is not None:
        owner_id = db.scalar(
            select(OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == "Active",
            )
            .order_by(OrganizationMember.id)
        )
        owner = db.get(User, owner_id) if owner_id else None
    if owner is None and organization_id is None:
        owner = db.scalar(select(User).order_by(User.id).limit(1))

    account = db.scalar(select(Account).order_by(Account.id).limit(1))
    contact = db.scalar(select(Contact).order_by(Contact.id).limit(1))
    lead = db.scalar(select(Lead).order_by(Lead.id).limit(1))
    if db.scalar(select(Product.id).limit(1)) is None and owner:
        db.add_all([
            Product(name="CONVOSIS CRM Enterprise", sku="YCR-ENT-001", category="CRM platform", unit_price=480000, stock_quantity=999, status="Active", description="Enterprise customer operations workspace.", owner_id=owner.id, organization_id=organization_id, related_type="accounts" if account else None, related_id=account.id if account else None),
            Product(name="Implementation Sprint", sku="YCR-SVC-010", category="Professional services", unit_price=125000, stock_quantity=20, status="Active", description="Guided onboarding and rollout package.", owner_id=owner.id, organization_id=organization_id, related_type="contacts" if contact else None, related_id=contact.id if contact else None),
        ])
    if db.scalar(select(Note.id).limit(1)) is None and owner and (account or lead):
        db.add(Note(title="Discovery notes", content="Capture the next stakeholder discussion and rollout priorities.", related_type="accounts" if account else "leads", related_id=account.id if account else lead.id, owner_id=owner.id, organization_id=organization_id))
    if db.scalar(select(Attachment.id).limit(1)) is None and owner and account:
        db.add(Attachment(name="Customer requirements.pdf", file_type="PDF", file_size="2.4 MB", url="#", related_type="accounts", related_id=account.id, owner_id=owner.id, organization_id=organization_id))
    if db.scalar(select(Email.id).limit(1)) is None and owner and contact:
        db.add(Email(subject="Follow-up and next steps", from_email=owner.email, to_email=contact.email, body="Sharing the next steps from our conversation.", status="Sent", sent_at=datetime.utcnow() - timedelta(hours=3), related_type="contacts", related_id=contact.id, owner_id=owner.id, organization_id=organization_id))
    db.commit()


def ensure_platform_defaults(db: Session, include_demo: bool = False) -> None:
    """Provision platform/setup records for the active organization only."""
    organization_id = TENANT_ORGANIZATION_ID.get()
    actor_id = TENANT_ACTOR_ID.get()
    admin = db.get(User, actor_id) if actor_id else None
    if admin is None and organization_id is not None:
        owner_id = db.scalar(
            select(OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == "Active",
            )
            .order_by(OrganizationMember.id)
        )
        admin = db.get(User, owner_id) if owner_id else None
    if admin is None and organization_id is None:
        admin = db.scalar(select(User).order_by(User.id))
    defaults: dict[str, list[dict[str, Any]]] = {
        "company_details": [{"name": "CONVOSIS CRM", "legal_name": "CONVOSIS CRM", "email": admin.email if admin else "admin@yashcrm.local", "status": "Active"}],
        "fiscal_years": [{"name": "April - March", "start_date": "2026-04-01", "end_date": "2027-03-31", "status": "Active"}],
        "roles": [{"name": "Administrator", "data_scope": "All", "status": "Active", "description": "Full record visibility."}, {"name": "Sales Manager", "parent_role": "Administrator", "data_scope": "Own and Subordinates", "status": "Active"}, {"name": "Sales Representative", "parent_role": "Sales Manager", "data_scope": "Own", "status": "Active"}],
        "profiles": [{"name": "Administrator", "permissions": {"all_modules": ["create", "read", "update", "delete", "export"], "setup": ["manage"]}, "status": "Active"}, {"name": "Standard", "permissions": {"crm_modules": ["create", "read", "update"], "setup": []}, "status": "Active"}],
        "permissions": [{"name": "CRM administrator", "module": "*", "grants": ["create", "read", "update", "delete", "export", "manage_setup"], "status": "Active"}],
        "pipelines": [{"name": "Default sales pipeline", "module": "Deals", "stages": [{"name": "Qualification", "probability": 20}, {"name": "Needs Analysis", "probability": 35}, {"name": "Proposal", "probability": 55}, {"name": "Negotiation", "probability": 75}, {"name": "Closed Won", "probability": 100, "closed": True}, {"name": "Closed Lost", "probability": 0, "closed": True}], "status": "Active"}],
        "custom_views": [{"name": "My open records", "module": "Deals", "filters": [{"field": "status", "operator": "equals", "value": "Open"}], "sort": "updated_desc", "columns": ["name", "account", "amount", "stage", "owner"], "status": "Active"}],
        "email_templates": [{"name": "Sales follow-up", "subject": "Next steps for {{account.name}}", "module": "Deals", "content": "Hello {{contact.first_name}},\n\nThank you for your time. Here are the agreed next steps.", "status": "Active"}],
        "quote_templates": [{"name": "Standard quote", "content": "Quote {{quote.quote_number}}\nCustomer: {{account.name}}\nTotal: {{quote.amount}}", "status": "Active"}],
        "invoice_templates": [{"name": "Standard invoice", "content": "Invoice {{invoice.invoice_number}}\nDue: {{invoice.due_date}}\nTotal: {{invoice.amount}}", "status": "Active"}],
        "api_settings": [{"name": "Local API", "scopes": ["crm.read", "crm.write"], "token_hint": "Generate credentials through your deployment secret manager", "status": "Inactive"}],
    }
    if include_demo:
        defaults.update({
            "price_books": [{"name": "Standard INR", "currency": "INR", "discount_percent": 0, "status": "Active", "description": "Default list pricing."}],
            "vendors": [{"name": "Sample Implementation Partner", "email": "partner@example.com", "category": "Professional services", "status": "Active"}],
            "campaigns": [{"name": "Customer success webinar", "campaign_type": "Webinar", "status": "Planned", "budget": 25000}],
            "cases": [{"name": "Sample onboarding question", "case_number": "CASE-1001", "priority": "Normal", "channel": "Web", "status": "New", "description": "Demonstration case for the local development workspace."}],
            "solutions": [{"name": "Getting started checklist", "category": "Onboarding", "status": "Published", "content": "Confirm owners, import clean data, configure the pipeline, and review permissions."}],
            "forecasts": [{"name": "Current quarter", "period": "Q4 2026", "target": 2500000, "committed": 0, "best_case": 0, "status": "Open"}],
            "reports": [{"name": "Open pipeline by stage", "module": "Deals", "report_type": "Summary", "filters": [{"field": "status", "value": "Open"}], "columns": ["stage", "count", "amount"], "status": "Active"}],
            "dashboards": [{"name": "Sales overview", "audience": "Sales team", "components": [{"type": "metric", "source": "open_deals"}, {"type": "pipeline", "source": "deals_by_stage"}], "status": "Active"}],
        })
    for resource, rows in defaults.items():
        count_query = select(func.count()).select_from(PlatformRecord).where(PlatformRecord.resource == resource)
        if organization_id is None:
            count_query = count_query.where(PlatformRecord.organization_id.is_(None))
        else:
            count_query = count_query.where(PlatformRecord.organization_id == organization_id)
        if db.scalar(count_query):
            continue
        for values in rows:
            record = PlatformRecord(
                resource=resource,
                title=str(values.get("name") or "Untitled"),
                data={},
                owner_id=admin.id if admin else actor_id,
                organization_id=organization_id,
            )
            sync_platform_columns(record, values)
            db.add(record)
    db.flush()


STAGE_PROBABILITY = {"Qualification": 20, "Needs Analysis": 40, "Proposal": 60, "Negotiation": 80, "Closed Won": 100, "Closed Lost": 0}
STAGE_STATUS = {"Closed Won": "Won", "Closed Lost": "Lost"}


def order_clauses(model: type[Base], sort: str) -> list[Any]:
    created = getattr(model, "created_at", model.id)
    if sort == "name_asc":
        for attrs in (("last_name", "first_name"), ("name",), ("subject",), ("title",)):
            if all(hasattr(model, attr) for attr in attrs):
                return [getattr(model, attr).asc() for attr in attrs]
        return [model.id.asc()]
    if sort == "amount_desc" and hasattr(model, "amount"):
        return [model.amount.desc()]
    if sort == "close_asc" and hasattr(model, "expected_close_date"):
        return [model.expected_close_date.asc()]
    if sort == "score_desc" and hasattr(model, "lead_score"):
        return [model.lead_score.desc()]
    return [created.desc(), model.id.desc()]


def list_resource(db: Session, resource: str, search: str | None, status: str | None, owner_id: int | None, sort: str, min_amount: float | None, max_amount: float | None, close_from: date | None, close_to: date | None, limit: int, offset: int, activity_type: str | None = None, actor: User | None = None) -> dict[str, Any]:
    model = RESOURCE_MAP[resource]
    query = select(model)
    if hasattr(model, "archived"):
        query = query.where(getattr(model, "archived") == False)
    if search:
        clauses = [getattr(model, column).ilike(f"%{search}%") for column in SEARCH_COLUMNS.get(resource, []) if hasattr(model, column)]
        if resource == "contacts":
            clauses.append((Contact.first_name + " " + Contact.last_name).ilike(f"%{search}%"))
        if clauses:
            query = query.where(or_(*clauses))
    if status:
        if resource == "deals" and status in STAGE_PROBABILITY:
            query = query.where(Deal.stage == status)
        elif hasattr(model, "status"):
            query = query.where(getattr(model, "status") == status)
        elif hasattr(model, "stage"):
            query = query.where(getattr(model, "stage") == status)
    if owner_id and hasattr(model, "owner_id"):
        query = query.where(getattr(model, "owner_id") == owner_id)
    if resource == "activities" and activity_type:
        query = query.where(Activity.activity_type == activity_type)
    if resource == "deals":
        if min_amount is not None:
            query = query.where(Deal.amount >= min_amount)
        if max_amount is not None:
            query = query.where(Deal.amount <= max_amount)
        if close_from:
            query = query.where(Deal.expected_close_date >= close_from)
        if close_to:
            query = query.where(Deal.expected_close_date <= close_to)
    all_rows = [row for row in db.scalars(query.order_by(*order_clauses(model, sort))).all() if _access_hook(db, resource, row, actor)]
    count = len(all_rows)
    rows = all_rows[offset:offset + limit]
    return {"items": [serialize(row, db, actor) for row in rows], "total": count, "limit": limit, "offset": offset}




__all__ = [
    "RESOURCE_MAP",
    "SEARCH_COLUMNS",
    "STAGE_PROBABILITY",
    "STAGE_STATUS",
    "TRANSACTION_NUMBERS",
    "_active_blueprint",
    "_execute_workflow_action",
    "_record_title",
    "_workflow_actions",
    "_workflow_condition",
    "_workflow_value",
    "add_audit",
    "apply_assignment_rule",
    "coerce_value",
    "configure_approval_hook",
    "configure_security_hooks",
    "enforce_blueprint_transition",
    "ensure_platform_defaults",
    "ensure_transaction_number",
    "ensure_workspace_defaults",
    "get_platform_reference",
    "json_safe",
    "list_resource",
    "normalize_platform_links",
    "order_clauses",
    "parse_date_value",
    "parse_datetime_value",
    "platform_config",
    "platform_values",
    "record_blueprint_transition",
    "refresh_invoice_balance",
    "related_label",
    "run_platform_automation",
    "run_record_automation",
    "seed_defaults",
    "serialize",
    "serialize_platform",
    "sync_platform_columns",
    "validate_platform_values",
    "workflow_criteria_match"
]
