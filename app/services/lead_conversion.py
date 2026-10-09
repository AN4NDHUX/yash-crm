from __future__ import annotations
from typing import Any
from fastapi import HTTPException
from sqlalchemy import select, func

def convert_lead(item_id: int, payload: RecordPayload, db: Session = Depends(get_db), actor: User | None = Depends(current_actor)) -> dict[str, Any]:
    # Delayed import avoids circular imports with the FastAPI route module.
    from app.main import (
        Lead, Account, Contact, Deal, Activity, Note, Attachment, Email, Product,
        PlatformRecord, MetadataModule, _custom_fields, LEAD_CONVERSION_LOCK,
        parse_date_value, can_access_record, serialize, add_audit,
    )
    lead = db.get(Lead, item_id)
    if lead is None or not can_access_record(db, "leads", lead, actor, "write"):
        raise HTTPException(404, "Lead not found")
    if lead.archived:
        raise HTTPException(409, "Archived leads cannot be converted")
    values = payload.model_dump(exclude_unset=True)
    create_deal = values.get("create_deal", True)
    if not isinstance(create_deal, bool):
        raise HTTPException(422, "create_deal must be a boolean")
    stage = str(values.get("stage") or "Qualification").strip()
    if create_deal and not values.get("expected_close_date"):
        raise HTTPException(422, "Closing date is required when creating a deal")
    close_date = parse_date_value(values.get("expected_close_date")) if create_deal else None
    # Guard against duplicate requests within the application process. The converted
    # linkage is also checked inside the lock for idempotent retries.
    with LEAD_CONVERSION_LOCK:
        db.refresh(lead)
        if lead.status == "Converted" and lead.converted_contact_id:
            account = db.get(Account, lead.converted_account_id) if lead.converted_account_id else None
            contact = db.get(Contact, lead.converted_contact_id)
            deal = db.get(Deal, lead.converted_deal_id) if lead.converted_deal_id else None
            return {"lead": serialize(lead, db, actor), "account": serialize(account, db, actor) if account else None, "contact": serialize(contact, db, actor), "deal": serialize(deal, db, actor) if deal else None}
        try:
            org_id = lead.organization_id
            def in_org(model):
                return model.organization_id == org_id

            company = str(values.get("account_name") or lead.company or "").strip()
            account = db.get(Account, lead.converted_account_id) if lead.converted_account_id else None
            if account is None and company:
                account = db.scalar(select(Account).where(func.lower(Account.name) == company.lower(), in_org(Account), Account.archived == False))
            if account is None and company:
                account = Account(name=company, phone=lead.phone, type="Prospect", owner_id=lead.owner_id, organization_id=org_id, status="Active", notes=f"Created from lead {lead.name}.", tags=["converted-lead"])
                db.add(account)
                db.flush()

            contact = db.get(Contact, lead.converted_contact_id) if lead.converted_contact_id else None
            if contact is None and lead.email:
                contact = db.scalar(select(Contact).where(func.lower(Contact.email) == lead.email.strip().lower(), in_org(Contact), Contact.archived == False))
            if contact is None:
                parts = lead.name.strip().split(" ", 1)
                contact = Contact(first_name=parts[0], last_name=parts[1] if len(parts) > 1 else "", email=lead.email, phone=lead.phone, account_id=account.id if account else None, owner_id=lead.owner_id, organization_id=org_id, notes=lead.notes or f"Converted from lead {lead.name}.", tags=lead.tags or ["converted"])
                db.add(contact)
                db.flush()
            elif account and contact.account_id is None:
                contact.account_id = account.id

            deal = db.get(Deal, lead.converted_deal_id) if lead.converted_deal_id else None
            if create_deal and deal is None:
                deal_name = str(values.get("deal_name") or (company or lead.name) + " opportunity").strip()
                if not deal_name:
                    raise HTTPException(422, "Deal name is required")
                deal = Deal(name=deal_name, account_id=account.id if account else None, contact_id=contact.id, amount=float(values.get("deal_amount") or 0), stage=stage, probability=20, expected_close_date=close_date, owner_id=lead.owner_id, organization_id=org_id, type="New business", source="Lead conversion", status="Open", notes=f"Created from lead #{lead.id} conversion. Contact role: {values.get('contact_role') or 'None'}")
                db.add(deal)
                db.flush()

            # Repoint related core records without copying or deleting them, preserving
            # their original identifiers, contents, attachments and history.
            target_type, target_id = ("deals", deal.id) if deal else ("contacts", contact.id)
            for model in (Activity, Note, Attachment, Email, Product):
                rows = db.scalars(select(model).where(model.related_type == "leads", model.related_id == lead.id, model.organization_id == org_id)).all()
                for row in rows:
                    row.related_type, row.related_id = target_type, target_id

            # Preserve lead-specific platform relationships, retaining the lead reference
            # for traceability while making them accessible through converted records.
            related_platform = db.scalars(select(PlatformRecord).where(PlatformRecord.organization_id == org_id, PlatformRecord.archived == False)).all()
            for row in related_platform:
                data = dict(row.data or {})
                linked = (row.related_type == "leads" and row.related_id == lead.id) or str(data.get("lead_id") or "") == str(lead.id)
                if linked:
                    if account and row.account_id is None: row.account_id = account.id
                    if row.contact_id is None: row.contact_id = contact.id
                    if deal and row.deal_id is None: row.deal_id = deal.id
                    # Keep existing custom field values and the lead lookup intact.
                    # Populate only declared and currently empty target lookup fields.
                    module = db.scalar(select(MetadataModule).where(
                        MetadataModule.api_name == row.resource,
                        MetadataModule.organization_id == org_id))
                    if module is not None:
                        declared = {field.api_name for field in _custom_fields(db, module.id)}
                        for field, reference in (
                            ("account_id", account.id if account else None),
                            ("contact_id", contact.id),
                            ("deal_id", deal.id if deal else None),
                        ):
                            if field in declared and reference is not None and data.get(field) in (None, ""):
                                data[field] = reference
                        if data != (row.data or {}):
                            row.data = data
                    if row.related_type == "leads" and row.related_id == lead.id:
                        row.related_type, row.related_id = target_type, target_id
            previous_status = lead.status
            lead.status = "Converted"
            lead.converted_account_id = account.id if account else None
            lead.converted_contact_id = contact.id
            lead.converted_deal_id = deal.id if deal else None
            add_audit(db, "convert", "leads", lead.id, f"Converted lead '{lead.name}'", before={"status": previous_status}, after={"account_id": lead.converted_account_id, "contact_id": contact.id, "deal_id": lead.converted_deal_id}, actor_id=lead.owner_id)
            db.commit()
            for record in (lead, account, contact, deal):
                if record is not None: db.refresh(record)
            return {"lead": serialize(lead, db, actor), "account": serialize(account, db, actor) if account else None, "contact": serialize(contact, db, actor), "deal": serialize(deal, db, actor) if deal else None}
        except Exception:
            db.rollback()
            raise

