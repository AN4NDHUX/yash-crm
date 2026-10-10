"""Immutable, per-organization CRM record numbering.

All numbers have a fixed alphabetic prefix and a five-digit numeric suffix.
The highest suffix across active AND archived records determines the next number.
PostgreSQL organization-row locks serialize allocations across app instances.
"""
from __future__ import annotations

import re
from threading import RLock

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, PlatformRecord, Product

NUMBER_DEFINITIONS = {
    "products": ("record_number", "PRD"),
    "price_books": ("record_number", "PB"),
    "vendors": ("record_number", "VND"),
    "quotes": ("quote_number", "QT"),
    "sales_orders": ("order_number", "SO"),
    "purchase_orders": ("po_number", "PO"),
    "invoices": ("invoice_number", "INV"),
    "payments": ("record_number", "PAY"),
}
NUMBER_FIELDS = frozenset(("record_number", "quote_number", "order_number", "po_number", "invoice_number"))
# SQLite tests and single-process deployments need an in-process allocation guard.
# PostgreSQL's row-level organization lock is the cross-process guard.
NUMBER_LOCK = RLock()


def protected_field(resource: str) -> str | None:
    return NUMBER_DEFINITIONS.get(resource, (None, None))[0]


def assert_number_immutable(resource: str, changes: dict, *, existing=None) -> None:
    if resource not in NUMBER_DEFINITIONS:
        return
    for key in NUMBER_FIELDS:
        if key in changes:
            raise HTTPException(422, f"{key} is generated automatically and cannot be edited")


def _sequence_suffix(raw: str | None, prefix: str) -> int:
    value = str(raw or "").strip().upper()
    if not value:
        return 0
    if value.startswith(prefix):
        # Current format: INV00001; historic format: INV-202610-00001.
        match = re.search(r"(\d+)$", value)
        return int(match.group(1)) if match else 0
    if prefix == "QT" and value.startswith("QUO"):
        match = re.search(r"(\d+)$", value)
        return int(match.group(1)) if match else 0
    return 0


def allocate_number(db: Session, resource: str, org_id: int | None) -> str:
    if resource not in NUMBER_DEFINITIONS:
        raise ValueError(f"Not a numbered resource: {resource}")
    if not org_id:
        raise HTTPException(409, "Organization must be assigned before numbering")
    # Lock remains held until caller commits, including on PostgreSQL.
    db.execute(select(Organization.id).where(Organization.id == org_id).with_for_update()).scalar_one()
    primary, prefix = NUMBER_DEFINITIONS[resource]
    biggest = 0
    if resource == "products":
        values = db.scalars(select(Product.record_number).where(Product.organization_id == org_id)).all()
        for raw in values:
            biggest = max(biggest, _sequence_suffix(raw, prefix))
    else:
        values = db.scalars(select(PlatformRecord.data).where(
            PlatformRecord.organization_id == org_id,
            PlatformRecord.resource == resource,
        )).all()
        for data in values:
            fields = data if isinstance(data, dict) else {}
            biggest = max(biggest, _sequence_suffix(fields.get("record_number"), prefix))
            biggest = max(biggest, _sequence_suffix(fields.get(primary), prefix))
    return f"{prefix}{biggest + 1:05d}"


def apply_number(db: Session, record: PlatformRecord | Product) -> str:
    resource = "products" if isinstance(record, Product) else record.resource
    field, _prefix = NUMBER_DEFINITIONS[resource]
    if isinstance(record, Product):
        if not record.record_number:
            record.record_number = allocate_number(db, resource, record.organization_id)
        return record.record_number
    data = dict(record.data or {})
    existing = str(data.get("record_number") or data.get(field) or "").strip()
    if not existing:
        existing = allocate_number(db, resource, record.organization_id)
    data["record_number"] = existing
    data[field] = existing
    record.record_number = existing
    record.data = data
    return existing
