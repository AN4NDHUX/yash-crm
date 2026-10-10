"""Idempotent organization-scoped Lead → Account/Contact → Deal lifecycle.

Account and Contact relationships are created when a Lead becomes Contacted.
A Deal is created only when that Lead becomes Converted. All mutations occur
in the caller's transaction, and rows are linked back to the original Lead.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, func


def _models():
    # Delayed import avoids circular imports with main.py.
    from app.main import (
        Lead, Account, Contact, Deal, Activity, Note, Attachment, Email, Product,
        PlatformRecord, MetadataModule, _custom_fields, LEAD_CONVERSION_LOCK,
        parse_date_value, can_access_record, serialize, add_audit, _enforce_record_limit,
    )
    return locals()


def _valid_link(db, model, record_id, org_id, label):
    if not record_id:
        return None
    record = db.get(model, record_id)
    if record is None or record.organization_id != org_id or record.archived:
        raise HTTPException(409, f"Linked {label} is missing, archived, or in another organization")
    return record


def ensure_contacted_parties(db, lead, actor) -> tuple[Any, Any]:
    """Create or link the corresponding Account and Contact exactly once.

    Match existing Accounts by company name; Contacts by normalized email or
    exact phone, scoped to the lead's organization. Blank identities are never
    used as a cross-lead deduplication key. Existing values are not overwritten.
    """
    m = _models()
    Account, Contact = m["Account"], m["Contact"]
    org_id = lead.organization_id
    if org_id is None:
        raise HTTPException(409, "A Lead needs an organization before it can be promoted")
    company = str(lead.company or "").strip() or str(lead.name or "").strip()
    if not company:
        raise HTTPException(422, "Lead name or company is required")
    account = _valid_link(db, Account, lead.converted_account_id, org_id, "Account")
    if account is None:
        account = db.scalar(select(Account).where(
            Account.organization_id == org_id, Account.archived == False,
            func.lower(func.trim(Account.name)) == company.casefold(),
        ).order_by(Account.id).limit(1))
    if account is None:
        m["_enforce_record_limit"](db, actor)
        account = Account(
            name=company, phone=lead.phone, type="Prospect", owner_id=lead.owner_id,
            organization_id=org_id, status="Active",
            notes=f"Created from lead #{lead.id}.", tags=["lead-contacted"],
        )
        db.add(account)
        db.flush()
        m["add_audit"](db, "create", "accounts", account.id,
                       f"Created Account from contacted lead #{lead.id}")
    if actor is not None and not m["can_access_record"](db, "accounts", account, actor):
        raise HTTPException(403, "Matching Account is not accessible")
    lead.converted_account_id = account.id

    contact = _valid_link(db, Contact, lead.converted_contact_id, org_id, "Contact")
    email = str(lead.email or "").strip().casefold()
    phone = str(lead.phone or "").strip()
    if contact is None and email:
        contact = db.scalar(select(Contact).where(
            Contact.organization_id == org_id, Contact.archived == False,
            func.lower(func.trim(Contact.email)) == email,
        ).order_by(Contact.id).limit(1))
    if contact is None and phone:
        # Never merge two people with conflicting populated email addresses.
        possible = db.scalars(select(Contact).where(
            Contact.organization_id == org_id, Contact.archived == False,
            func.trim(Contact.phone) == phone,
        ).order_by(Contact.id)).all()
        contact = next((row for row in possible if not email or not row.email
                        or str(row.email).strip().casefold() == email), None)
    if contact is None:
        m["_enforce_record_limit"](db, actor)
        names = str(lead.name or "").strip().split(" ", 1)
        contact = Contact(
            first_name=names[0], last_name=names[1] if len(names) > 1 else "",
            email=lead.email, phone=lead.phone, account_id=account.id,
            owner_id=lead.owner_id, organization_id=org_id,
            notes=lead.notes or f"Created from contacted lead #{lead.id}.",
            tags=lead.tags or ["lead-contacted"],
        )
        db.add(contact)
        db.flush()
        m["add_audit"](db, "create", "contacts", contact.id,
                       f"Created Contact from contacted lead #{lead.id}")
    elif contact.account_id is None:
        contact.account_id = account.id
    if actor is not None and not m["can_access_record"](db, "contacts", contact, actor):
        raise HTTPException(403, "Matching Contact is not accessible")
    lead.converted_contact_id = contact.id
    db.flush()
    return account, contact


def _relink_related_records(db, lead, account, contact, deal):
    """Preserve related core/custom records and their original lead lineage."""
    m = _models()
    org_id = lead.organization_id
    target_type, target_id = ("deals", deal.id) if deal else ("contacts", contact.id)
    for model in (m["Activity"], m["Note"], m["Attachment"], m["Email"], m["Product"]):
        rows = db.scalars(select(model).where(
            model.related_type == "leads", model.related_id == lead.id,
            model.organization_id == org_id,
        )).all()
        for row in rows:
            row.related_type, row.related_id = target_type, target_id

    PlatformRecord, MetadataModule = m["PlatformRecord"], m["MetadataModule"]
    for row in db.scalars(select(PlatformRecord).where(
        PlatformRecord.organization_id == org_id, PlatformRecord.archived == False,
    )).all():
        data = dict(row.data or {})
        linked = ((row.related_type == "leads" and row.related_id == lead.id)
                  or str(data.get("lead_id") or "") == str(lead.id))
        if not linked:
            continue
        if account and row.account_id is None:
            row.account_id = account.id
        if row.contact_id is None:
            row.contact_id = contact.id
        if deal and row.deal_id is None:
            row.deal_id = deal.id
        module = db.scalar(select(MetadataModule).where(
            MetadataModule.api_name == row.resource, MetadataModule.organization_id == org_id))
        if module is not None:
            declared = {field.api_name for field in m["_custom_fields"](db, module.id)}
            for field, reference in (
                ("account_id", account.id if account else None),
                ("contact_id", contact.id), ("deal_id", deal.id if deal else None),
            ):
                if field in declared and reference is not None and data.get(field) in (None, ""):
                    data[field] = reference
            if data != (row.data or {}):
                row.data = data
        if row.related_type == "leads" and row.related_id == lead.id:
            row.related_type, row.related_id = target_type, target_id


def promote_lead_to_deal(db, lead, actor, values=None, *, create_deal=True):
    """Complete promotion without committing, so the caller controls atomicity."""
    m = _models()
    Account, Contact, Deal = m["Account"], m["Contact"], m["Deal"]
    values = values or {}
    account, contact = ensure_contacted_parties(db, lead, actor)
    org_id = lead.organization_id
    deal = _valid_link(db, Deal, lead.converted_deal_id, org_id, "Deal")
    if deal is None:
        deal = db.scalar(select(Deal).where(
            Deal.organization_id == org_id,
            Deal.origin_lead_id == lead.id,
            Deal.archived == False,
        ).limit(1))
    if create_deal and deal is None:
        m["_enforce_record_limit"](db, actor)
        name = str(values.get("deal_name") or lead.name).strip()
        if not name:
            raise HTTPException(422, "Deal name is required")
        close_date = (m["parse_date_value"](values["expected_close_date"])
                      if values.get("expected_close_date") else None)
        stage = str(values.get("stage") or "Qualification").strip()
        deal = Deal(
            name=name, account_id=account.id, contact_id=contact.id, phone=lead.phone,
            origin_lead_id=lead.id, amount=float(values.get("deal_amount") or 0),
            stage=stage, probability=20, expected_close_date=close_date,
            owner_id=lead.owner_id, organization_id=org_id, type="New business",
            source=lead.source or "Lead conversion", status="Open",
            notes=(lead.notes or "") + f"\nOrigin Lead #{lead.id}; role: {values.get('contact_role') or 'None'}",
        )
        db.add(deal)
        db.flush()
        m["add_audit"](db, "create", "deals", deal.id,
                       f"Created Deal from converted lead #{lead.id}")
    if deal and not deal.origin_lead_id:
        deal.origin_lead_id = lead.id
    if deal:
        lead.converted_deal_id = deal.id
    _relink_related_records(db, lead, account, contact, deal)
    lead.status = "Converted"
    db.flush()
    return account, contact, deal


def apply_lead_stage_lifecycle(db, lead, actor):
    """Called by record creation/update/import when the Lead stage is changed."""
    status = str(lead.status or "").casefold().strip()
    if status == "contacted":
        return ensure_contacted_parties(db, lead, actor)
    if status == "converted":
        return promote_lead_to_deal(db, lead, actor)
    return None


def convert_lead_service(item_id, payload, db, actor, *, automatic=False, commit=True) -> dict[str, Any]:
    m = _models()
    Lead, Account, Contact, Deal = m["Lead"], m["Account"], m["Contact"], m["Deal"]
    values = payload.model_dump(exclude_unset=True)
    create_deal = values.get("create_deal", True)
    if not isinstance(create_deal, bool):
        raise HTTPException(422, "create_deal must be a boolean")
    if create_deal and not automatic and not values.get("expected_close_date"):
        raise HTTPException(422, "Closing date is required when creating a deal")
    if values.get("expected_close_date"):
        m["parse_date_value"](values["expected_close_date"])
    with m["LEAD_CONVERSION_LOCK"]:
        lead = db.scalar(select(Lead).where(Lead.id == item_id).with_for_update())
        if lead is None or not m["can_access_record"](db, "leads", lead, actor, "write"):
            raise HTTPException(404, "Lead not found")
        if lead.archived:
            raise HTTPException(409, "Archived leads cannot be converted")
        if lead.status == "Converted" and lead.converted_contact_id and (not create_deal or lead.converted_deal_id):
            account = _valid_link(db, Account, lead.converted_account_id, lead.organization_id, "Account")
            contact = _valid_link(db, Contact, lead.converted_contact_id, lead.organization_id, "Contact")
            deal = _valid_link(db, Deal, lead.converted_deal_id, lead.organization_id, "Deal")
        else:
            try:
                previous = lead.status
                account, contact, deal = promote_lead_to_deal(
                    db, lead, actor, values, create_deal=create_deal,
                )
                m["add_audit"](db, "convert", "leads", lead.id,
                               f"Converted lead '{lead.name}'",
                               before={"status": previous},
                               after={"account_id": account.id, "contact_id": contact.id,
                                      "deal_id": deal.id if deal else None},
                               actor_id=lead.owner_id)
                if commit:
                    db.commit()
                    for row in (lead, account, contact, deal):
                        if row is not None:
                            db.refresh(row)
            except Exception:
                if commit:
                    db.rollback()
                raise
        return {
            "lead": m["serialize"](lead, db, actor),
            "account": m["serialize"](account, db, actor) if account else None,
            "contact": m["serialize"](contact, db, actor),
            "deal": m["serialize"](deal, db, actor) if deal else None,
        }
