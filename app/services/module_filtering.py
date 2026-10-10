"""Validated, access-scoped list-view filters for four core CRM modules.

The filter engine only uses persisted fields and real record relationships.
Filters run before pagination; no ad-hoc SQL or arbitrary attribute paths.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.sql.sqltypes import String, Text, Integer, Float, Numeric, Date, DateTime, Boolean

from app.models import (
    Lead, Account, Contact, Deal, Activity, Email, Note, Attachment,
    PlatformRecord,
)

CORE_MODELS = {"leads": Lead, "accounts": Account, "contacts": Contact, "deals": Deal}
RELATED_MODELS = {
    "leads": Lead, "accounts": Account, "contacts": Contact, "deals": Deal,
    "activities": Activity, "emails": Email, "notes": Note, "attachments": Attachment,
}
RELATIONSHIPS = {
    "leads": ("accounts", "contacts", "deals", "activities", "emails", "notes", "attachments"),
    "deals": ("accounts", "contacts", "leads", "activities", "emails", "notes", "attachments",
              "quotes", "sales_orders", "invoices"),
    "accounts": ("contacts", "deals", "leads", "activities", "emails", "notes", "attachments",
                 "quotes", "sales_orders", "invoices", "cases", "documents"),
    "contacts": ("accounts", "deals", "leads", "activities", "emails", "notes", "attachments",
                 "quotes", "cases", "documents"),
}
SYSTEM_FILTERS = {
    "leads": (("touched", "Touched records"), ("untouched", "Untouched records"),
              ("converted", "Converted leads"), ("unconverted", "Unconverted leads")),
    "deals": (("touched", "Touched records"), ("untouched", "Untouched records"),
              ("open", "Open deals"), ("closed", "Closed deals")),
    "accounts": (("touched", "Touched records"), ("untouched", "Untouched records")),
    "contacts": (("touched", "Touched records"), ("untouched", "Untouched records")),
}
EXCLUDED_FIELDS = {
    "id", "organization_id", "archived", "tags", "layout_name",
    "converted_account_id", "converted_contact_id", "converted_deal_id",
}
NAME_OVERRIDES = {
    "owner_id": "Record owner", "lead_score": "Lead score",
    "next_follow_up": "Next follow-up", "expected_close_date": "Closing date",
    "created_at": "Created time", "updated_at": "Modified time",
}


def _field_type(column: Any) -> str | None:
    if isinstance(column.type, (Date, DateTime)):
        return "date"
    if isinstance(column.type, (Integer, Float, Numeric)):
        return "number"
    if isinstance(column.type, Boolean):
        return "boolean"
    if isinstance(column.type, (String, Text)):
        return "text"
    return None


def catalog(resource: str) -> dict[str, Any]:
    if resource not in CORE_MODELS:
        raise HTTPException(status_code=404, detail="Filters unavailable for this module")
    model = CORE_MODELS[resource]
    fields = [
        {
            "key": column.name,
            "label": NAME_OVERRIDES.get(
                column.name, column.name.replace("_", " ").title()
            ),
            "type": kind,
        }
        for column in model.__table__.columns
        if column.name not in EXCLUDED_FIELDS
        for kind in [_field_type(column)]
        if kind is not None
    ]
    return {
        "resource": resource,
        "fields": fields,
        "system": [
            {"key": key, "label": label} for key, label in SYSTEM_FILTERS[resource]
        ],
        "related": [
            {"key": key, "label": key.replace("_", " ").title()}
            for key in RELATIONSHIPS[resource]
        ],
    }


def _bad_filter(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def parse_filters(resource: str, raw: str | None) -> tuple[str, list[dict[str, Any]]]:
    if resource not in CORE_MODELS or not raw:
        return "all", []
    if len(raw) > 6000:
        raise _bad_filter("Filter specification is too large")
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise _bad_filter("Filters must contain valid JSON") from exc
    if not isinstance(parsed, dict) or parsed.get("join", "all") not in {"all", "any"}:
        raise _bad_filter("Invalid filter combination")
    rules = parsed.get("rules", [])
    if not isinstance(rules, list) or len(rules) > 12:
        raise _bad_filter("A maximum of 12 filter conditions is supported")
    available = catalog(resource)
    fields = {field["key"]: field["type"] for field in available["fields"]}
    system = {entry["key"] for entry in available["system"]}
    related = {entry["key"] for entry in available["related"]}
    operators = {"equals", "not_equals", "contains", "gt", "gte", "lt", "lte",
                 "is_empty", "is_not_empty"}
    normalized: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise _bad_filter("Invalid filter condition")
        kind, key, op = rule.get("kind"), rule.get("key"), rule.get("operator")
        value = rule.get("value", "")
        if not isinstance(value, str) or len(value) > 200:
            raise _bad_filter("Filter values must be text under 200 characters")
        if kind == "field":
            if key not in fields or op not in operators:
                raise _bad_filter("Unsupported field filter")
            field_type = fields[key]
            if op == "contains" and field_type != "text":
                raise _bad_filter("Contains is only supported for text fields")
            if field_type == "boolean" and op not in {"equals", "not_equals", "is_empty", "is_not_empty"}:
                raise _bad_filter("Unsupported boolean comparison")
            if op not in {"is_empty", "is_not_empty"}:
                if not value.strip():
                    raise _bad_filter("Provide a value for the selected field")
                if field_type == "number":
                    try:
                        float(value)
                    except ValueError as exc:
                        raise _bad_filter("Numeric filter requires a valid number") from exc
                if field_type == "date":
                    try:
                        date.fromisoformat(value[:10])
                    except ValueError as exc:
                        raise _bad_filter("Date filter requires YYYY-MM-DD") from exc
                if field_type == "boolean" and value.lower() not in {"true", "false"}:
                    raise _bad_filter("Boolean filters require true or false")
        elif kind == "related":
            if key not in related or op not in {"exists", "not_exists"}:
                raise _bad_filter("Unsupported related-module filter")
            if op == "not_exists" and value.strip():
                raise _bad_filter("Without-related filters do not accept a search term")
        elif kind == "system":
            if key not in system or op != "enabled":
                raise _bad_filter("Unsupported system filter")
        else:
            raise _bad_filter("Invalid filter type")
        normalized.append({"kind": kind, "key": key, "operator": op, "value": value.strip()})
    return parsed.get("join", "all"), normalized


def _same_org(parent: Any, child: Any) -> bool:
    first = getattr(parent, "organization_id", None)
    second = getattr(child, "organization_id", None)
    if first is not None or second is not None:
        # Never combine records across different organizations, including an
        # organization-stamped record with a legacy unscoped record.
        return first is not None and first == second
    # Some legacy/test records predate tenant-stamping. Only their same-owner
    # relationships can be followed, after per-record permission checks.
    first_owner = getattr(parent, "owner_id", None)
    second_owner = getattr(child, "owner_id", None)
    return first_owner is not None and first_owner == second_owner


def _matches_link(parent: Any, module: str, child: Any, related: str) -> bool:
    if not _same_org(parent, child):
        return False
    if related in {"activities", "emails", "notes", "attachments"}:
        key = str(child.related_type or "").strip().lower()
        return key in {module, module.rstrip("s")} and child.related_id == parent.id
    if related == "accounts":
        return (module == "contacts" and parent.account_id == child.id) or (
            module == "deals" and parent.account_id == child.id) or (
            module == "leads" and parent.converted_account_id == child.id)
    if related == "contacts":
        return (module == "deals" and parent.contact_id == child.id) or (
            module == "leads" and parent.converted_contact_id == child.id) or (
            module == "accounts" and child.account_id == parent.id)
    if related == "deals":
        return (module == "accounts" and child.account_id == parent.id) or (
            module == "contacts" and child.contact_id == parent.id) or (
            module == "leads" and parent.converted_deal_id == child.id)
    if related == "leads":
        return (module == "accounts" and child.converted_account_id == parent.id) or (
            module == "contacts" and child.converted_contact_id == parent.id) or (
            module == "deals" and child.converted_deal_id == parent.id)
    # Platform modules are supported only where the stored foreign key establishes
    # a real relationship; unrelated platform rows must not match.
    if isinstance(child, PlatformRecord):
        if module == "accounts":
            return child.account_id == parent.id or (
                child.related_type in {"account", "accounts"} and child.related_id == parent.id)
        if module == "contacts":
            return child.contact_id == parent.id or (
                child.related_type in {"contact", "contacts"} and child.related_id == parent.id)
        if module == "deals":
            return child.deal_id == parent.id or (
                child.related_type in {"deal", "deals"} and child.related_id == parent.id)
    return False


def _related_title(child: Any) -> str:
    if isinstance(child, Contact):
        return f"{child.first_name} {child.last_name}"
    return str(getattr(child, "title", None) or getattr(child, "name", None)
               or getattr(child, "subject", None) or "")


def _field_matches(record: Any, rule: dict[str, Any], kind: str) -> bool:
    raw = getattr(record, rule["key"], None)
    op, desired = rule["operator"], rule["value"]
    if op == "is_empty":
        return raw is None or raw == ""
    if op == "is_not_empty":
        return raw is not None and raw != ""
    if raw is None:
        return op == "not_equals"
    if kind == "number":
        left, right = float(raw), float(desired)
    elif kind == "date":
        left = raw.date() if isinstance(raw, datetime) else raw
        right = date.fromisoformat(desired[:10])
    elif kind == "boolean":
        left, right = bool(raw), desired.lower() == "true"
    else:
        left, right = str(raw).casefold(), desired.casefold()
    return {
        "equals": lambda: left == right,
        "not_equals": lambda: left != right,
        "contains": lambda: right in left,
        "gt": lambda: left > right,
        "gte": lambda: left >= right,
        "lt": lambda: left < right,
        "lte": lambda: left <= right,
    }[op]()


def _system_matches(record: Any, key: str) -> bool:
    if key == "touched":
        return record.updated_at is not None and record.created_at is not None and record.updated_at > record.created_at
    if key == "untouched":
        return record.updated_at is None or record.created_at is None or record.updated_at <= record.created_at
    if key == "converted":
        return record.status == "Converted"
    if key == "unconverted":
        return record.status != "Converted"
    if key == "open":
        return record.stage not in {"Closed Won", "Closed Lost"}
    if key == "closed":
        return record.stage in {"Closed Won", "Closed Lost"}
    return False


def filter_rows(
    db: Any,
    resource: str,
    rows: list[Any],
    raw_filters: str | None,
    actor: Any,
    access_check: Callable[..., bool],
) -> list[Any]:
    join, rules = parse_filters(resource, raw_filters)
    if not rules:
        return rows
    field_types = {field["key"]: field["type"] for field in catalog(resource)["fields"]}
    related_rows: dict[str, list[Any]] = {}
    for rule in rules:
        if rule["kind"] != "related" or rule["key"] in related_rows:
            continue
        key = rule["key"]
        if key in RELATED_MODELS:
            candidates = db.scalars(select(RELATED_MODELS[key]).where(
                RELATED_MODELS[key].archived == False  # noqa: E712
            )).all()
        else:
            candidates = db.scalars(select(PlatformRecord).where(
                PlatformRecord.resource == key,
                PlatformRecord.archived == False,  # noqa: E712
            )).all()
        related_rows[key] = [
            candidate for candidate in candidates
            if access_check(db, key, candidate, actor)
        ]
    def matches(record: Any, rule: dict[str, Any]) -> bool:
        kind, key = rule["kind"], rule["key"]
        if kind == "field":
            # Filtering must not expose values redacted by a user's field profile.
            from app.services.core import serialize
            safe = serialize(record, db, actor)
            if key not in safe:
                return False
            return _field_matches_record_value(safe[key], rule, field_types[key])
        if kind == "system":
            return _system_matches(record, key)
        needle = rule["value"].casefold()
        exists = any(
            _matches_link(record, resource, child, key)
            and (not needle or needle in _related_title(child).casefold())
            for child in related_rows[key]
        )
        return exists if rule["operator"] == "exists" else not exists

    return [
        row for row in rows
        if (all(matches(row, rule) for rule in rules) if join == "all"
            else any(matches(row, rule) for rule in rules))
    ]


def _field_matches_record_value(raw: Any, rule: dict[str, Any], kind: str) -> bool:
    # Reuse the validated comparison while evaluating the authorized serialized
    # representation, not an unrestricted model attribute.
    class RecordValue:
        pass
    wrapper = RecordValue()
    setattr(wrapper, rule["key"], raw)
    if raw is None or isinstance(raw, (str, int, float, bool, datetime, date)):
        if kind == "date" and isinstance(raw, str) and raw:
            try:
                setattr(wrapper, rule["key"], date.fromisoformat(raw[:10]))
            except ValueError:
                return False
        return _field_matches(wrapper, rule, kind)
    return False
