"""Backfill immutable per-module numbers for products and sales documents.

Existing document identifiers remain stable; records without an identifier are
given the next number after the highest numeric suffix in that tenant/module.
"""
from __future__ import annotations

import json
import re

from alembic import op
import sqlalchemy as sa

revision = "0029_sales_record_numbering"
down_revision = "0028_deal_origin_lead"
branch_labels = None
depends_on = None

PREFIX = {
    "products": ("record_number", "PRD"),
    "price_books": ("record_number", "PB"),
    "vendors": ("record_number", "VND"),
    "quotes": ("quote_number", "QT"),
    "sales_orders": ("order_number", "SO"),
    "purchase_orders": ("po_number", "PO"),
    "invoices": ("invoice_number", "INV"),
    "payments": ("record_number", "PAY"),
}


def suffix(raw, prefix):
    raw = str(raw or "").strip().upper()
    if not raw.startswith(prefix) and not (prefix == "QT" and raw.startswith("QUO")):
        return 0
    m = re.search(r"(\d+)$", raw)
    return int(m.group(1)) if m else 0


def upgrade():
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("record_number", sa.String(48), nullable=True))
    with op.batch_alter_table("platform_records") as batch:
        batch.add_column(sa.Column("record_number", sa.String(48), nullable=True))
    db = op.get_bind()
    biggest = {}
    taken = {}
    records = []
    for row in db.execute(sa.text(
        "SELECT id, organization_id, record_number FROM products ORDER BY id"
    )).mappings():
        key = (row["organization_id"], "products")
        number = str(row["record_number"] or "").strip()
        records.append(("products", row["id"], key, {}, number))
        biggest[key] = max(biggest.get(key, 0), suffix(number, "PRD"))
    for row in db.execute(sa.text(
        "SELECT id, organization_id, resource, data, record_number "
        "FROM platform_records ORDER BY id"
    )).mappings():
        resource = row["resource"]
        if resource not in PREFIX:
            continue
        body = row["data"] or {}
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (ValueError, TypeError):
                body = {}
        body = dict(body) if isinstance(body, dict) else {}
        field, prefix = PREFIX[resource]
        key = (row["organization_id"], resource)
        number = str(row["record_number"] or body.get("record_number") or body.get(field) or "").strip()
        records.append(("platform_records", row["id"], key, body, number))
        for raw in (number, body.get(field), body.get("record_number")):
            biggest[key] = max(biggest.get(key, 0), suffix(raw, prefix))
    for table, ident, key, body, existing in records:
        resource = key[1]
        field, prefix = PREFIX[resource]
        seen = taken.setdefault(key, set())
        number = existing
        if not number or number.casefold() in seen:
            biggest[key] = biggest.get(key, 0) + 1
            number = f"{prefix}{biggest[key]:05d}"
        seen.add(number.casefold())
        if table == "products":
            db.execute(sa.text("UPDATE products SET record_number=:number WHERE id=:id"),
                       {"number": number, "id": ident})
        else:
            body["record_number"] = number
            body[field] = number
            db.execute(sa.text(
                "UPDATE platform_records SET record_number=:number, data=:body WHERE id=:id"
            ).bindparams(sa.bindparam("body", type_=sa.JSON())),
                {"number": number, "body": body, "id": ident})
    with op.batch_alter_table("products") as batch:
        batch.create_unique_constraint("uq_product_org_record_number", ["organization_id", "record_number"])
    with op.batch_alter_table("platform_records") as batch:
        batch.create_unique_constraint(
            "uq_platform_org_resource_number", ["organization_id", "resource", "record_number"]
        )


def downgrade():
    with op.batch_alter_table("platform_records") as batch:
        batch.drop_constraint("uq_platform_org_resource_number", type_="unique")
        batch.drop_column("record_number")
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("uq_product_org_record_number", type_="unique")
        batch.drop_column("record_number")
