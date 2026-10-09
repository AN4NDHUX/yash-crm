"""Tenant- and permission-scoped Zoho-style CRM task adapter.

These tasks target records in CONVOSIS CRM. They DO NOT call Zoho's servers.
Every call must be made from a recognized workflow actor in an active workspace.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.database import TENANT_ORGANIZATION_ID, TENANT_ACTOR_ID
from app.models import OrganizationMember, User
from app.services.core import RESOURCE_MAP, serialize, _execute_workflow_action, coerce_value
from app.services.security import (
    can_access_record, authorize_field_values, _profile_action_allowed,
    _enforce_record_limit,
)

# User and administration records are explicitly excluded from scripted tasks.
MODULES = {"leads", "contacts", "accounts", "deals", "products"}
PROTECTED = {
    "id", "organization_id", "owner_id", "created_by", "created_at",
    "updated_at", "password", "password_hash", "membership_role",
    "is_platform_owner", "version", "archived",
}
CRITERION = re.compile(r"^\(([A-Za-z][A-Za-z0-9_]{0,79}):(equals|starts_with|contains):([^()]*)\)$")


def _context(db):
    organization_id = TENANT_ORGANIZATION_ID.get()
    actor_id = TENANT_ACTOR_ID.get()
    if not isinstance(organization_id, int) or not isinstance(actor_id, int):
        raise ValueError("Zoho-style CRM task requires an authenticated workspace context")
    actor = db.get(User, actor_id)
    member = db.scalar(select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == actor_id,
        OrganizationMember.status == "Active",
    ))
    if actor is None or actor.status != "Active" or member is None:
        raise ValueError("CRM task actor is not an active member of the workspace")
    return organization_id, actor


def _module(module: Any):
    if not isinstance(module, str):
        raise ValueError("CRM module must be a string")
    key = module.lower().strip().replace(" ", "_")
    if key not in MODULES:
        raise ValueError("CRM module is not exposed to scripted integration tasks")
    return key, RESOURCE_MAP[key]


def _scope(model, organization_id):
    if "organization_id" not in model.__table__.columns:
        raise ValueError("Scripted module is not organization-scoped")
    query = select(model).where(model.organization_id == organization_id)
    if "archived" in model.__table__.columns:
        query = query.where(model.archived == False)
    return query


def _require(db, actor, module, access):
    if not _profile_action_allowed(db, actor, module, access):
        raise ValueError(f"CRM {access} permission denied for {module}")


def _editable(db, actor, module, model, fields):
    if not isinstance(fields, dict) or not 1 <= len(fields) <= 40:
        raise ValueError("CRM task field map must contain 1–40 fields")
    if any(not isinstance(k, str) or not k.isidentifier() or k.startswith("_")
           or k.lower() in PROTECTED or k not in model.__table__.columns
           for k in fields):
        raise ValueError("CRM task field map contains an unrecognized or protected field")
    authorize_field_values(db, module, fields, actor, "write")
    if any(isinstance(v, (list, dict)) and len(v) > 100 for v in fields.values()):
        raise ValueError("CRM task field values exceed allowed limits")


def _one(db, module, model, org, actor, record_id, access="read"):
    if type(record_id) is not int or record_id <= 0:
        raise ValueError("CRM record ID must be a positive integer")
    record = db.scalar(_scope(model, org).where(model.id == record_id))
    if record is None or not can_access_record(db, module, record, actor, access):
        raise ValueError("CRM record not found or inaccessible")
    return record


def run_crm_task(db, name: str, args: list, *, source_resource: str):
    if not isinstance(args, (list, tuple)) or len(args) > 5:
        raise ValueError("Invalid CRM integration task arguments")
    org, actor = _context(db)
    if not args:
        raise ValueError("CRM integration task requires a module")
    module, model = _module(args[0])
    if name not in {"getRecordById", "getRecords", "searchRecords", "createRecord", "updateRecord", "deleteRecord"}:
        raise ValueError("Unsupported CRM integration task")
    if name in {"getRecordById", "getRecords", "searchRecords"}:
        _require(db, actor, module, "read")
        if name == "getRecordById":
            if len(args) < 2:
                raise ValueError("getRecordById requires a record ID")
            record = _one(db, module, model, org, actor, args[1])
            return serialize(record, db, actor)
        # Bound every database query before applying access filters.
        rows = list(db.scalars(_scope(model, org).order_by(model.id).limit(1000)).all())
        rows = [r for r in rows if can_access_record(db, module, r, actor, "read")]
        if name == "getRecords":
            page = args[2] if len(args) > 2 and args[2] is not None else 1
            per_page = args[3] if len(args) > 3 and args[3] is not None else 20
            if type(page) is not int or type(per_page) is not int or not 1 <= page <= 50 or not 1 <= per_page <= 100:
                raise ValueError("Invalid CRM pagination")
            start = (page - 1) * per_page
            return [serialize(r, db, actor) for r in rows[start:start + per_page]]
        if len(args) < 2 or not isinstance(args[1], str):
            raise ValueError("searchRecords requires a criteria string")
        match = CRITERION.fullmatch(args[1])
        if match is None:
            raise ValueError("Only one bounded Zoho search criterion is supported")
        field, operator, expected = match.groups()
        if field not in model.__table__.columns or field.lower() in PROTECTED:
            raise ValueError("Cannot search a protected or unknown field")
        from app.services.security import field_allowed
        if not field_allowed(db, module, field, actor, "read"):
            raise ValueError("Search field access denied")
        matched = []
        for row in rows:
            actual = str(getattr(row, field) or "")
            if (operator == "equals" and actual == expected or
                operator == "starts_with" and actual.startswith(expected) or
                operator == "contains" and expected in actual):
                matched.append(serialize(row, db, actor))
        return matched[:100]

    if name == "createRecord":
        _require(db, actor, module, "create")
        if module == source_resource:
            raise ValueError("CRM task cannot create a record in its own trigger module")
        if len(args) < 2:
            raise ValueError("createRecord requires a field map")
        fields = args[1]
        _editable(db, actor, module, model, fields)
        _enforce_record_limit(db, actor)
        data = {k: coerce_value(model, k, v) for k, v in fields.items()}
        if "owner_id" in model.__table__.columns:
            data["owner_id"] = actor.id
        data["organization_id"] = org
        record = model(**data)
        db.add(record)
        db.flush()
        return {"id": record.id, "status": "success"}

    if len(args) < 2:
        raise ValueError("Record ID is required")
    action = "delete" if name == "deleteRecord" else "update"
    _require(db, actor, module, action)
    record = _one(db, module, model, org, actor, args[1], "delete" if action == "delete" else "edit")
    if name == "deleteRecord":
        if "archived" not in model.__table__.columns:
            raise ValueError("Module does not support safe deletion")
        record.archived = True
        db.flush()
        return {"id": record.id, "status": "success"}

    if len(args) < 3:
        raise ValueError("updateRecord requires a field map")
    fields = args[2]
    _editable(db, actor, module, model, fields)
    for field, value in fields.items():
        _execute_workflow_action(db, {"type": "field_update", "field": field, "value": value},
                                 module, record, fields)
    db.flush()
    return {"id": record.id, "status": "success"}
