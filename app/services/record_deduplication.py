"""Organization-scoped duplicate detection for core CRM modules.

Uses nonempty business identifiers only. Different Deals may legitimately
share a title when they concern different Account/Contact combinations.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, func, or_, and_

from app.database import TENANT_ORGANIZATION_ID
from app.models import Lead, Account, Contact, Deal


def reject_duplicate(db, resource, values, *, exclude_id=None):
    org = values.get("organization_id") or TENANT_ORGANIZATION_ID.get()
    if not org or resource not in {"leads", "accounts", "contacts", "deals"}:
        return
    model = {"leads": Lead, "accounts": Account, "contacts": Contact, "deals": Deal}[resource]
    clauses = []
    def normalized(field, key=None):
        v = str(values.get(key or field) or "").strip()
        return v.casefold() if v else ""

    email = normalized("email")
    phone = normalized("phone")
    name = normalized("name")
    if resource in {"leads", "contacts"}:
        if email:
            clauses.append(func.lower(func.trim(model.email)) == email)
        if phone:
            clauses.append(func.trim(model.phone) == phone)
    elif resource == "accounts" and name:
        clauses.append(func.lower(func.trim(model.name)) == name)
    elif resource == "deals":
        if values.get("origin_lead_id"):
            clauses.append(Deal.origin_lead_id == values["origin_lead_id"])
        if name:
            clauses.append(and_(
                func.lower(func.trim(Deal.name)) == name,
                Deal.account_id == values.get("account_id"),
                Deal.contact_id == values.get("contact_id"),
            ))
    if not clauses:
        return
    stmt = select(model.id).where(model.organization_id == org, model.archived == False, or_(*clauses))
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    existing = db.scalar(stmt.limit(1))
    if existing is not None:
        raise HTTPException(409, f"Duplicate {resource.rstrip('s')} exists (record #{existing}). Link or update the existing record instead.")
