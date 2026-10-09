"""Published Blueprint selection and safe, bounded transition configuration.

Blueprint matching is evaluated against a single tenant's record. Drafts never
override default CRM stages. Historical JSON Blueprints remain supported.
"""
from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Blueprint, BlueprintTransitionLog
from app.database import TENANT_ORGANIZATION_ID

FIELDS = {"leads": "status", "deals": "stage"}
# Picklist-type native record fields that can safely control process states.
STATE_FIELDS = {"leads": {"status", "source"}, "deals": {"stage", "status", "type"}}
CRITERIA_FIELDS = {
    "leads": {"status", "name", "company", "email", "source", "lead_score"},
    "deals": {"stage", "name", "amount", "probability", "source", "status"},
}
OPS = {"is", "is_not", "contains", "not_contains", "starts_with", "ends_with", "is_empty", "is_not_empty", "greater_than", "less_than"}
ACTIONS = {"create_task", "tag", "field_update", "audit", "notification"}


def _fail(detail):
    raise HTTPException(422, detail=detail)


def validate_blueprint(data: dict[str, Any], publish: bool = False) -> dict[str, Any]:
    module = str(data.get("module") or "Leads").lower().strip()
    if module not in FIELDS:
        _fail("Visual Blueprints currently support Leads and Deals")
    field = str(data.get("field_name") or FIELDS[module])
    if field not in STATE_FIELDS[module]:
        _fail("Blueprint stages require an editable single-choice field. Text, number, date, and unsupported custom fields cannot control process states.")
    name = str(data.get("name") or "").strip()
    if not 1 <= len(name) <= 160:
        _fail("Blueprint name is required (maximum 160 characters)")
    layout = str(data.get("layout_name") or "Default").strip()
    if not 1 <= len(layout) <= 100:
        _fail("Invalid layout")
    conditions = data.get("entry_conditions") or []
    if not isinstance(conditions, list) or len(conditions) > 12:
        _fail("Entry criteria may have at most 12 conditions")
    for cond in conditions:
        if not isinstance(cond, dict) or cond.get("field") not in CRITERIA_FIELDS[module] or cond.get("operator") not in OPS:
            _fail("Unknown entry criteria field or operator")
        if len(str(cond.get("value") or "")) > 500:
            _fail("Entry criteria value is too long")
    states = data.get("stages") or []
    transitions = data.get("transitions") or []
    if not isinstance(states, list) or len(states) > 40 or not isinstance(transitions, list) or len(transitions) > 100:
        _fail("Too many Blueprint states or transitions")
    labels = []
    for stage in states:
        if not isinstance(stage, dict) or not 1 <= len(str(stage.get("label") or "").strip()) <= 80:
            _fail("Each state needs a label (maximum 80 characters)")
        labels.append(str(stage["label"]).strip())
        if not isinstance(stage.get("x", 0), (int, float)) or not isinstance(stage.get("y", 0), (int, float)):
            _fail("Invalid state position")
    if len(labels) != len(set(labels)):
        _fail("State labels must be unique")
    for edge in transitions:
        if not isinstance(edge, dict) or edge.get("from") not in labels or edge.get("to") not in labels or edge["from"] == edge["to"]:
            _fail("Each transition must connect two different saved states")
        if not 1 <= len(str(edge.get("label") or "").strip()) <= 100:
            _fail("Transition label is required")
        if edge.get("owner_scope", "any") not in {"any", "owner"}:
            _fail("Invalid transition owner restriction")
        required = edge.get("required") or []
        if not isinstance(required, list) or len(required) > 15 or any(field not in CRITERIA_FIELDS[module] for field in required):
            _fail("Invalid required transition fields")
        actions = edge.get("after") or []
        if not isinstance(actions, list) or len(actions) > 10:
            _fail("Too many after-transition actions")
        for action in actions:
            if not isinstance(action, dict) or action.get("type") not in ACTIONS:
                _fail("Unsupported after-transition action")
            if action["type"] == "field_update" and action.get("field") not in CRITERIA_FIELDS[module] - {field}:
                _fail("Blueprint actions cannot modify the controlled state field")
    if publish and (not states or not transitions):
        _fail("Publish requires at least two states and one transition")
    return {"name": name, "module": module.title(), "layout_name": layout, "field_name": field,
            "description": str(data.get("description") or "")[:2000],
            "entry_conditions": conditions, "entry_criteria": "",
            "stages": states, "transitions": transitions,
            "transition_requirements": [
                {"transition": edge["label"], "required": edge.get("required") or []}
                for edge in transitions
            ], "continuous": bool(data.get("continuous")),
            "draft": not publish, "active": bool(publish)}


def matches_conditions(conditions: Any, row: dict[str, Any], module: str) -> bool:
    if not conditions:
        return True
    if not isinstance(conditions, list):
        return False
    for cond in conditions:
        if not isinstance(cond, dict) or cond.get("field") not in CRITERIA_FIELDS.get(module, set()) or cond.get("operator") not in OPS:
            return False
        actual = row.get(cond["field"])
        target = cond.get("value")
        op = cond["operator"]
        x, y = str(actual or "").casefold(), str(target or "").casefold()
        try:
            numeric = float(actual), float(target)
        except (TypeError, ValueError):
            numeric = None
        ok = {"is": x == y, "is_not": x != y,
              "contains": y in x, "not_contains": y not in x,
              "starts_with": x.startswith(y), "ends_with": x.endswith(y),
              "is_empty": actual in (None, ""), "is_not_empty": actual not in (None, ""),
              "greater_than": bool(numeric and numeric[0] > numeric[1]),
              "less_than": bool(numeric and numeric[0] < numeric[1])}[op]
        if not ok:
            return False
    return True


def matching_blueprint(db, resource: str, record: Any) -> Blueprint | None:
    if resource not in FIELDS or record is None:
        return None
    org = getattr(record, "organization_id", None)
    if type(org) is not int or org != TENANT_ORGANIZATION_ID.get():
        return None
    candidates = db.scalars(select(Blueprint).where(
        Blueprint.organization_id == org, Blueprint.active == True,
        Blueprint.draft == False, Blueprint.archived == False,
    ).order_by(Blueprint.id.desc())).all()
    row = {c.name: getattr(record, c.key) for c in record.__table__.columns}
    for bp in candidates:
        if str(bp.module or "").strip().lower().rstrip("s") != resource.rstrip("s"):
            continue
        if (bp.layout_name or "Default") != (getattr(record, "layout_name", None) or "Default"):
            continue
        if (bp.field_name or FIELDS[resource]) not in STATE_FIELDS[resource]:
            continue
        # A previously transitioned record remains enrolled when its state changes.
        enrolled = db.scalar(select(BlueprintTransitionLog.id).where(
            BlueprintTransitionLog.blueprint_id == bp.id,
            BlueprintTransitionLog.module == resource,
            BlueprintTransitionLog.record_id == record.id,
        ).limit(1)) is not None
        if not enrolled and bp.entry_conditions and not matches_conditions(bp.entry_conditions, row, resource):
            continue
        if bp.entry_criteria and not enrolled:
            # Legacy free-form criteria cannot be evaluated safely as code.
            # Accept only an explicit legacy JSON conditions array.
            try:
                legacy = json.loads(bp.entry_criteria)
            except (ValueError, TypeError):
                continue
            if not matches_conditions(legacy, row, resource):
                continue
        return bp
    return None


def transition_choices(bp: Blueprint, current: str) -> list[dict[str, Any]]:
    choices = []
    for index, edge in enumerate(bp.transitions or []):
        if not isinstance(edge, dict) or (edge.get("from") != current and not edge.get("common")):
            continue
        dest = str(edge.get("to") or "")
        if not dest or dest == current:
            continue
        choices.append({"id": str(edge.get("id") or index), "label": str(edge.get("label") or dest),
                        "to": dest, "from": current, "message": str(edge.get("message") or "")[:1000],
                        "required": edge.get("required") or [], "owner_scope": edge.get("owner_scope", "any")})
    return choices


def find_transition(bp: Blueprint, from_state: str, selector: str) -> dict[str, Any] | None:
    for index, edge in enumerate(bp.transitions or []):
        if not isinstance(edge, dict):
            continue
        if str(edge.get("id") or index) == selector and (edge.get("from") == from_state or edge.get("common")):
            return edge
    return None
