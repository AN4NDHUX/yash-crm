"""Visual Blueprint creation, publication and execution routes."""
from __future__ import annotations
from typing import Any
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.sql.sqltypes import String as SQLString
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Blueprint, PlatformRecord, User, MetadataModule, MetadataField
from app.schemas import RecordPayload
from app.services.core import RESOURCE_MAP, serialize, add_audit
from app.services.security import _enforce_record_limit, can_access_record


def mount_blueprint_routes(app, current_actor, _require_organization_admin):
    # The visual editor uses strictly validated structured data. Legacy JSON endpoints
    # remain readable so existing automations and Blueprint transition history survive.
    @app.get("/api/blueprint-designer/options")
    def blueprint_designer_options(module: str = "leads", db: Session = Depends(get_db), actor: User = Depends(current_actor)) -> dict[str, Any]:
        """Expose field-specific criteria values from the current organization's records."""
        from app.services.blueprint_engine import FIELDS, CRITERIA_FIELDS, STATE_FIELDS
        from app.services.core import STAGE_PROBABILITY
        from app.models import Lead, Deal

        organization, _ = _require_organization_admin(db, actor)
        module = module.lower().strip()
        if module not in FIELDS:
            raise HTTPException(422, "Choose Leads or Deals")
        layouts = ["Default"]
        for row in db.scalars(select(PlatformRecord).where(
            PlatformRecord.organization_id == organization.id,
            PlatformRecord.resource == "layouts", PlatformRecord.archived == False,
        )).all():
            if str((row.data or {}).get("module", "")).lower().rstrip("s") == module.rstrip("s"):
                layouts.append(row.title)

        defaults = {
            "leads": {
                "status": ["New", "Contacted", "Qualified", "Unqualified", "Converted"],
                "source": ["Website", "Referral", "LinkedIn", "Event", "Outbound", "Other"],
            },
            "deals": {
                "stage": list(STAGE_PROBABILITY),
                "status": ["Open", "Won", "Lost"],
                "type": ["New business", "Expansion", "Renewal", "Partnership"],
            },
        }
        label_overrides = {
            "lead_score": "Lead Score", "source": "Lead Source" if module == "leads" else "Source",
            "stage": "Deal Stage", "status": "Lead Status" if module == "leads" else "Deal Status",
        }
        model = Lead if module == "leads" else Deal
        native_labels = {
            "name": "Lead Name" if module == "leads" else "Deal Name",
            "company": "Company", "email": "Email", "phone": "Phone",
            "source": "Lead Source" if module == "leads" else "Source",
            "status": "Lead Status" if module == "leads" else "Deal Status",
            "stage": "Deal Stage", "type": "Deal Type", "lead_score": "Lead Score",
            "next_follow_up": "Next Follow-up", "expected_close_date": "Closing Date",
            "owner_id": "Record Owner", "account_id": "Account", "contact_id": "Contact",
            "probability": "Probability", "amount": "Amount", "layout_name": "Layout",
            "notes": "Notes", "tags": "Tags",
        }
        internal_columns = {"id", "organization_id", "archived", "created_at", "updated_at",
                            "converted_account_id", "converted_contact_id", "converted_deal_id"}
        all_fields = []
        for column in model.__table__.columns:
            field = column.name
            if field in internal_columns:
                continue
            supported = field in STATE_FIELDS[module]
            all_fields.append({
                "name": field,
                "label": native_labels.get(field, field.replace("_", " ").title()),
                "supported": supported,
                "reason": "" if supported else "Not an editable single-choice field",
            })
        for custom in db.scalars(select(PlatformRecord).where(
            PlatformRecord.organization_id == organization.id,
            PlatformRecord.resource == "custom_fields",
            PlatformRecord.archived == False,
        )).all():
            data = custom.data or {}
            if str(data.get("module") or "").strip().lower().rstrip("s") != module.rstrip("s"):
                continue
            key = str(data.get("api_name") or "").strip()
            if not key or any(field["name"] == key for field in all_fields):
                continue
            all_fields.append({
                "name": key, "label": str(data.get("name") or custom.title or key)[:100],
                "supported": False, "reason": "Custom fields are not yet mapped to native record state transitions",
            })
        # Include fields configured through the metadata module builder.
        # These entries are discoverable but cannot control ORM record states.
        builder_ids = db.scalars(select(MetadataModule.id).where(
            MetadataModule.organization_id == organization.id,
            MetadataModule.api_name == module,
            MetadataModule.enabled == True,
        )).all()
        if builder_ids:
            for definition in db.scalars(select(MetadataField).where(
                MetadataField.module_id.in_(builder_ids),
            ).order_by(MetadataField.position, MetadataField.id)).all():
                if any(item["name"] == definition.api_name for item in all_fields):
                    continue
                all_fields.append({
                    "name": definition.api_name,
                    "label": definition.label,
                    "supported": False,
                    "reason": "Custom metadata field is not mapped to core record transitions",
                })
        criteria_meta = {}
        for field in sorted(CRITERIA_FIELDS[module]):
            column = getattr(model, field)
            is_numeric = not isinstance(column.property.columns[0].type, SQLString)
            values = list(defaults[module].get(field, []))
            statement = (
                select(column)
                .where(model.organization_id == organization.id, model.archived == False, column.is_not(None))
                .distinct()
                .order_by(column)
                .limit(100)
            )
            for observed in db.scalars(statement).all():
                if observed is None or str(observed).strip() == "":
                    continue
                value = str(observed)
                if value not in values:
                    values.append(value)
            criteria_meta[field] = {
                "label": label_overrides.get(field, field.replace("_", " ").title()),
                "type": "number" if is_numeric else "select" if field in defaults[module] else "text",
                "options": values[:120],
                "allow_custom": field not in defaults[module],
            }
        return {
            "fields": all_fields,
            "criteria_fields": sorted(CRITERIA_FIELDS[module]),
            "criteria_meta": criteria_meta,
            "layouts": list(dict.fromkeys(layouts)),
            "initial_states": defaults["leads"]["status"][:4] if module == "leads" else list(STAGE_PROBABILITY),
            "state_values": defaults[module],
        }


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
        edge = find_transition(bp, str(getattr(record, bp.field_name or FIELDS[resource]) or ""), identifier)
        if edge is None:
            raise HTTPException(422, "The selected Blueprint transition is not available")
        extra = payload.get("fields") or {}
        if not isinstance(extra, dict) or any(k not in CRITERIA_FIELDS[resource] - {bp.field_name or FIELDS[resource]} for k in extra):
            raise HTTPException(422, "Only allowed CRM fields can be updated during the transition")
        data = dict(extra)
        data[bp.field_name or FIELDS[resource]] = edge["to"]
        # Route through the same permission, Blueprint and workflow validations as normal editing.
        from app.main import update_record
        if resource == "leads" and (bp.field_name or FIELDS[resource]) == "status" and edge["to"] == "Converted":
            from app.services.lead_conversion import BLUEPRINT_CONVERSION_CONTEXT
            token = BLUEPRINT_CONVERSION_CONTEXT.set(True)
            try:
                return update_record(resource, item_id, RecordPayload(**data), db=db, actor=actor)
            finally:
                BLUEPRINT_CONVERSION_CONTEXT.reset(token)
        return update_record(resource, item_id, RecordPayload(**data), db=db, actor=actor)
