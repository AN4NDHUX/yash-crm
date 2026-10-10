"""Five-step guided import API for Leads, Deals, Accounts and Contacts.

Kept independent of the main FastAPI application to preserve module boundaries.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db, TENANT_ORGANIZATION_ID
from app.models import User, MetadataModule, MetadataLayout, OrganizationMember, Activity, ImportJob
from app.services.core import (
    RESOURCE_MAP, STAGE_PROBABILITY, STAGE_STATUS, coerce_value,
    run_record_automation, add_audit, apply_assignment_rule,
)
from app.services.security import (
    current_actor, authorize_field_values, can_access_record, _enforce_record_limit,
)
from app.services.import_wizard import parse_import_file, MAX_IMPORT_ROWS, MAX_FILE_BYTES
from app.services.record_deduplication import reject_duplicate
from app.services.lead_conversion import apply_lead_stage_lifecycle

router = APIRouter()


@router.get("/api/import-wizard/{resource}/sample.{format}")
def guided_import_sample(resource: str, format: str, actor: User = Depends(current_actor)) -> StreamingResponse:
    templates = {
        "leads": ["First Name", "Last Name", "Phone Number", "Lead Source", "Lead Status"],
        "deals": ["Deal Name", "Phone Number", "Amount", "Stage"],
        "accounts": ["Account Name", "Phone Number", "Website", "Industry"],
        "contacts": ["First Name", "Last Name", "Phone Number", "Email"],
    }
    if resource not in templates or format not in {"csv", "xlsx"}:
        raise HTTPException(404, "Unknown import sample")
    columns = templates[resource]
    if format == "csv":
        stream = io.StringIO()
        csv.writer(stream).writerow(columns)
        payload = stream.getvalue().encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
    else:
        from openpyxl import Workbook
        book = Workbook()
        book.active.title = resource.title()
        book.active.append(columns)
        binary = io.BytesIO()
        book.save(binary)
        payload = binary.getvalue()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamingResponse(iter([payload]), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="crm-{resource}-sample.{format}"'
    })


# Guided import endpoints are separate from the legacy CSV endpoint, preserving its
# existing integrations while applying strict mapping and phone validation to the wizard.

async def _wizard_uploads(files: list[UploadFile], charset: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not 1 <= len(files) <= 3:
        raise HTTPException(422, "Select 1–3 files")
    parsed = [parse_import_file(file.filename or "", await file.read(MAX_FILE_BYTES + 1), charset) for file in files]
    columns = parsed[0]["columns"]
    if any(part["columns"] != columns for part in parsed[1:]):
        raise HTTPException(422, "All files must have identical columns for one import")
    if sum(part["count"] for part in parsed) > MAX_IMPORT_ROWS:
        raise HTTPException(413, "Only 100,000 records can be imported per job")
    return parsed, columns


@router.post("/api/import-wizard/{resource}/preview")
async def preview_guided_import(
    resource: str, files: list[UploadFile] = File(...),
    charset: str = Form("auto"), actor: User = Depends(current_actor),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    if resource not in {"leads", "deals", "accounts", "contacts"}:
        raise HTTPException(404, "Unknown import module")
    parsed, columns = await _wizard_uploads(files, charset)
    module = db.scalars(select(MetadataModule).where(MetadataModule.api_name == resource)).first()
    layouts = ["Default"]
    if module is not None:
        layouts.extend(str(name) for name in db.scalars(select(MetadataLayout.name).where(
            MetadataLayout.module_id == module.id)).all() if name and str(name) not in layouts)
    return {"resource": resource, "layouts": layouts, "files": [{"name": p["filename"], "count": p["count"]} for p in parsed],
            "columns": columns, "sample": parsed[0]["sample"],
            "total": sum(p["count"] for p in parsed),
            "fields": [{"key": key, "label": key.replace("_", " ").title()}
                       for key in RESOURCE_MAP[resource].__table__.columns.keys()
                       if key not in {"id", "created_at", "updated_at", "organization_id",
                                      "owner_id", "archived", "converted_account_id",
                                      "converted_contact_id", "converted_deal_id"}]}


@router.post("/api/import-wizard/{resource}/submit")
async def submit_guided_import(
    resource: str, files: list[UploadFile] = File(...), mapping: str = Form(...),
    charset: str = Form("auto"), operation: str = Form("add"),
    duplicate_key: str = Form("none"), layout: str = Form("Default"),
    trigger_automation: bool = Form(False), apply_assignment: bool = Form(False),
    followup_task: str = Form(""),
    db: Session = Depends(get_db), actor: User = Depends(current_actor)
) -> dict[str, Any]:
    if resource not in {"leads", "deals", "accounts", "contacts"}:
        raise HTTPException(404, "Unknown import module")
    if operation not in {"add", "update", "both"}:
        raise HTTPException(422, "Invalid import operation")
    if duplicate_key not in {"none", "phone", "email", "id"}:
        raise HTTPException(422, "Invalid duplicate rule")
    if operation in {"update", "both"} and duplicate_key == "none":
        raise HTTPException(422, "Select a matching field to update records")
    if operation in {"update", "both"}:
        from app.services.security import _profile_action_allowed
        if not _profile_action_allowed(db, actor, resource, "update"):
            raise HTTPException(403, "Your profile does not allow updating these records")
    parsed, columns = await _wizard_uploads(files, charset)
    try:
        field_map = json.loads(mapping)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Invalid field mapping") from exc
    if not isinstance(field_map, dict):
        raise HTTPException(422, "Field mapping must be an object")
    model = RESOURCE_MAP[resource]
    restricted = {"id", "owner_id", "organization_id", "archived",
                  "created_at", "updated_at", "converted_account_id",
                  "converted_contact_id", "converted_deal_id", "lead_score"}
    available = set(model.__table__.columns.keys()) - restricted
    if any(k not in columns or not isinstance(v, str) or v not in available
           for k, v in field_map.items()):
        raise HTTPException(422, "Mapping contains an unknown or restricted field")
    if len(set(field_map.values())) != len(field_map):
        raise HTTPException(422, "Each CRM field can only be mapped once")
    if "phone" not in field_map.values():
        raise HTTPException(422, "Phone Number must be mapped before continuing")
    required_field = "first_name" if resource == "contacts" else "name"
    if required_field not in field_map.values():
        raise HTTPException(422, f"{required_field.replace('_', ' ').title()} must be mapped")
    if resource == "contacts" and "last_name" not in field_map.values():
        raise HTTPException(422, "Last Name must be mapped for Contacts")
    if duplicate_key == "email" and "email" not in model.__table__.columns:
        raise HTTPException(422, "Email matching is not supported for this module")
    if duplicate_key != "none" and duplicate_key != "id" and duplicate_key not in field_map.values():
        raise HTTPException(422, "The duplicate matching field must also be mapped")
    if len(layout) > 100:
        raise HTTPException(422, "Invalid layout name")
    followup_task = followup_task.strip()
    if len(followup_task) > 180:
        raise HTTPException(422, "Follow-up task subject is too long")
    if followup_task:
        from app.services.security import _profile_action_allowed
        if not _profile_action_allowed(db, actor, "activities", "create"):
            raise HTTPException(403, "Your profile does not allow creating follow-up tasks")

    imported, updated, skipped, errors = 0, 0, 0, []
    for part in parsed:
        for row_number, row in enumerate(part["rows"], start=2):
            try:
                with db.begin_nested():
                    raw_values = {field: row.get(column, "").strip()
                                  for column, field in field_map.items()
                                  if row.get(column, "").strip()}
                    if resource == "leads" and raw_values.get("name"):
                        # Zoho spreadsheets frequently split lead names into first and last.
                        # Preserve both components when the Last Name column maps to name.
                        name_column = next((column for column, field in field_map.items() if field == "name"), "")
                        if name_column.strip().casefold() == "last name":
                            first = str(row.get("First Name") or row.get("First_Name") or "").strip()
                            if first:
                                raw_values["name"] = f"{first} {raw_values['name']}"
                    if not raw_values.get("phone"):
                        raise HTTPException(422, "Phone Number cannot be empty")
                    if not raw_values.get(required_field):
                        raise HTTPException(422, f"{required_field.replace('_', ' ').title()} cannot be empty")
                    if resource == "contacts" and not raw_values.get("last_name"):
                        raise HTTPException(422, "Last Name cannot be empty for Contacts")
                    values = {key: coerce_value(model, key, val) for key, val in raw_values.items()}
                    authorize_field_values(db, resource, values, actor, "write")
                    match = None
                    if duplicate_key != "none":
                        if duplicate_key == "id":
                            record_id = row.get("id") or row.get("ID") or ""
                            if str(record_id).strip().isdigit():
                                match = db.get(model, int(record_id))
                        else:
                            check_value = str(raw_values.get(duplicate_key) or "").strip()
                            if check_value:
                                match = db.scalars(select(model).where(
                                    func.lower(getattr(model, duplicate_key)) == check_value.lower(),
                                    model.archived == False
                                ).order_by(model.id)).first()
                        if match is not None and (getattr(match, "archived", False)
                                                  or not can_access_record(db, resource, match, actor)):
                            raise HTTPException(403, "Matching record is not accessible")
                    if match is not None:
                        if operation == "add":
                            skipped += 1
                            continue
                        if resource == "leads" and match.status == "Converted":
                            raise HTTPException(409, "Converted Leads are read-only")
                        for key, value in values.items():
                            setattr(match, key, value)
                        reject_duplicate(db, resource, {col.key:getattr(match,col.key) for col in model.__table__.columns}, exclude_id=match.id)
                        db.flush()
                        if resource == "leads":
                            apply_lead_stage_lifecycle(db, match, actor)
                        if trigger_automation:
                            run_record_automation(db, resource, "update", match, values)
                        add_audit(db, "import_update", resource, match.id, "Updated through guided import")
                        updated += 1
                    elif operation == "update":
                        skipped += 1
                    else:
                        _enforce_record_limit(db, actor)
                        if resource == "leads":
                            from app.services.stage_scoring import default_mapping, score_transition
                            values["lead_score"] = score_transition("", values.get("status") or "New", default_mapping())["stage_score"]
                        if resource in {"leads", "deals"} and "layout_name" in model.__table__.columns:
                            values["layout_name"] = layout or "Default"
                        if resource == "deals":
                            stage = values.get("stage", "Qualification")
                            values.setdefault("probability", STAGE_PROBABILITY.get(stage, 20))
                            values.setdefault("status", STAGE_STATUS.get(stage, "Open"))
                        if apply_assignment:
                            apply_assignment_rule(db, resource, values)
                            candidate = values.get("owner_id")
                            if candidate and not db.scalar(select(OrganizationMember.id).where(
                                OrganizationMember.organization_id == TENANT_ORGANIZATION_ID.get(),
                                OrganizationMember.user_id == candidate,
                                OrganizationMember.status == "Active",
                            )):
                                values.pop("owner_id", None)
                        values.setdefault("owner_id", actor.id)
                        reject_duplicate(db, resource, values)
                        record = model(**values)
                        db.add(record)
                        db.flush()
                        if resource == "leads":
                            apply_lead_stage_lifecycle(db, record, actor)
                        if trigger_automation:
                            run_record_automation(db, resource, "create", record, values)
                        if followup_task:
                            task = Activity(
                                organization_id=TENANT_ORGANIZATION_ID.get(),
                                activity_type="Task", subject=followup_task,
                                owner_id=record.owner_id, due_at=datetime.utcnow() + timedelta(days=1),
                                related_type=resource, related_id=record.id,
                                status="Open",
                            )
                            db.add(task)
                            db.flush()
                            add_audit(db, "create", "activities", task.id, "Follow-up task from guided import")
                        add_audit(db, "import", resource, record.id, "Created through guided import")
                        imported += 1
            except Exception as exc:
                errors.append({"file": part["filename"], "row": row_number,
                               "error": str(getattr(exc, "detail", exc))[:240]})
    job = ImportJob(owner_id=actor.id, organization_id=TENANT_ORGANIZATION_ID.get(),
                    resource=resource, filename=", ".join(p["filename"] for p in parsed)[:220],
                    status="Completed with errors" if errors else "Completed",
                    total_rows=imported + updated + skipped + len(errors),
                    imported_rows=imported + updated, error_rows=len(errors), errors=errors[:100])
    db.add(job)
    db.commit()
    return {"job_id": job.id, "resource": resource, "imported": imported, "updated": updated,
            "skipped": skipped, "errors": errors, "status": job.status}


