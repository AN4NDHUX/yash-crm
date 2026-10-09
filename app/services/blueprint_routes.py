"""Visual Blueprint creation, publication and execution routes."""
from __future__ import annotations
from typing import Any
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Blueprint, PlatformRecord, User
from app.schemas import RecordPayload
from app.services.core import RESOURCE_MAP, serialize, add_audit
from app.services.security import _enforce_record_limit, can_access_record


def mount_blueprint_routes(app, current_actor, _require_organization_admin):
    # The visual editor uses strictly validated structured data. Legacy JSON endpoints
    # remain readable so existing automations and Blueprint transition history survive.
    @app.get("/api/blueprint-designer/options")
    def blueprint_designer_options(module: str = "leads", db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        from app.services.blueprint_engine import FIELDS, CRITERIA_FIELDS
        organization, _ = _require_organization_admin(db, actor)
        module = module.lower()
        if module not in FIELDS:
            raise HTTPException(422, "Choose Leads or Deals")
        layouts = ["Default"]
        for row in db.scalars(select(PlatformRecord).where(
            PlatformRecord.organization_id == organization.id,
            PlatformRecord.resource == "layouts", PlatformRecord.archived == False,
        )).all():
            if str((row.data or {}).get("module", "")).lower().rstrip("s") == module.rstrip("s"):
                layouts.append(row.title)
        from app.services.core import STAGE_PROBABILITY
        return {"fields": [{"name": FIELDS[module], "label": "Lead Status" if module == "leads" else "Deal Stage"}],
                "criteria_fields": sorted(CRITERIA_FIELDS[module]), "layouts": list(dict.fromkeys(layouts)),
                "initial_states": ["New", "Contacted", "Qualified", "Unqualified"] if module == "leads" else list(STAGE_PROBABILITY)}
    
    
    @app.get("/api/blueprint-designer")
    def blueprint_designer_list(db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        organization, _ = _require_organization_admin(db, actor)
        rows = db.scalars(select(Blueprint).where(Blueprint.organization_id == organization.id, Blueprint.archived == False).order_by(Blueprint.updated_at.desc(), Blueprint.id.desc())).all()
        return {"items": [serialize(item, db, actor) for item in rows], "total": len(rows)}
    
    
    @app.post("/api/blueprint-designer", status_code=201)
    def blueprint_designer_create(payload: dict[str, Any], db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        from app.services.blueprint_engine import validate_blueprint
        organization, _ = _require_organization_admin(db, actor)
        _enforce_record_limit(db, actor)
        values = validate_blueprint(payload, publish=False)
        bp = Blueprint(**values, organization_id=organization.id)
        db.add(bp)
        db.flush()
        add_audit(db, "blueprint_draft", "blueprints", bp.id, "Created visual Blueprint draft", actor_id=actor.id)
        db.commit()
        db.refresh(bp)
        return serialize(bp, db, actor)
    
    
    @app.get("/api/blueprint-designer/{blueprint_id}")
    def blueprint_designer_detail(blueprint_id: int, db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        organization, _ = _require_organization_admin(db, actor)
        bp = db.get(Blueprint, blueprint_id)
        if bp is None or bp.archived or bp.organization_id != organization.id:
            raise HTTPException(404, "Blueprint not found")
        return serialize(bp, db, actor)
    
    
    @app.put("/api/blueprint-designer/{blueprint_id}")
    def blueprint_designer_save(blueprint_id: int, payload: dict[str, Any], db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        from app.services.blueprint_engine import validate_blueprint
        organization, _ = _require_organization_admin(db, actor)
        bp = db.get(Blueprint, blueprint_id)
        if bp is None or bp.archived or bp.organization_id != organization.id:
            raise HTTPException(404, "Blueprint not found")
        values = validate_blueprint(payload, publish=False)
        for key, value in values.items():
            setattr(bp, key, value)
        # Editing an active process requires an explicit re-publish.
        add_audit(db, "blueprint_draft", "blueprints", bp.id, "Saved Blueprint as draft", actor_id=actor.id)
        db.commit()
        db.refresh(bp)
        return serialize(bp, db, actor)
    
    
    @app.post("/api/blueprint-designer/{blueprint_id}/publish")
    def blueprint_designer_publish(blueprint_id: int, db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        from app.services.blueprint_engine import validate_blueprint
        organization, _ = _require_organization_admin(db, actor)
        bp = db.get(Blueprint, blueprint_id)
        if bp is None or bp.archived or bp.organization_id != organization.id:
            raise HTTPException(404, "Blueprint not found")
        source = serialize(bp, db, actor)
        values = validate_blueprint(source, publish=True)
        for key, value in values.items():
            setattr(bp, key, value)
        add_audit(db, "blueprint_publish", "blueprints", bp.id, "Published visual Blueprint", actor_id=actor.id)
        db.commit()
        db.refresh(bp)
        return serialize(bp, db, actor)
    
    
    @app.post("/api/blueprint-designer/{blueprint_id}/deactivate")
    def blueprint_designer_deactivate(blueprint_id: int, db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        organization, _ = _require_organization_admin(db, actor)
        bp = db.get(Blueprint, blueprint_id)
        if bp is None or bp.archived or bp.organization_id != organization.id:
            raise HTTPException(404, "Blueprint not found")
        bp.active = False
        add_audit(db, "blueprint_deactivate", "blueprints", bp.id, "Deactivated Blueprint", actor_id=actor.id)
        db.commit()
        return serialize(bp, db, actor)
    
    
    @app.post("/api/blueprint-records/{resource}/{item_id}/transition")
    def apply_record_blueprint_transition(resource: str, item_id: int, payload: dict[str, Any], db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        from app.services.blueprint_engine import FIELDS, matching_blueprint, find_transition, CRITERIA_FIELDS
        if resource not in FIELDS:
            raise HTTPException(404, "Blueprint transition not supported for resource")
        record = db.get(RESOURCE_MAP[resource], item_id)
        if record is None or getattr(record, "archived", False) or not can_access_record(db, resource, record, actor, "write"):
            raise HTTPException(404, "Record not found")
        bp = matching_blueprint(db, resource, record)
        if bp is None:
            raise HTTPException(409, "No published Blueprint matches this record")
        identifier = str(payload.get("transition_id") or "")
        edge = find_transition(bp, str(getattr(record, FIELDS[resource]) or ""), identifier)
        if edge is None:
            raise HTTPException(422, "The selected Blueprint transition is not available")
        extra = payload.get("fields") or {}
        if not isinstance(extra, dict) or any(k not in CRITERIA_FIELDS[resource] - {FIELDS[resource]} for k in extra):
            raise HTTPException(422, "Only allowed CRM fields can be updated during the transition")
        data = dict(extra)
        data[FIELDS[resource]] = edge["to"]
        # Route through the same permission, Blueprint and workflow validations as normal editing.
        from app.main import update_record
        return update_record(resource, item_id, RecordPayload(**data), db=db, actor=actor)
