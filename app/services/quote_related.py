"""Permission-scoped Quote related lists and audit timeline."""
from sqlalchemy import select
from app.models import PlatformRecord, Note, Attachment, Email, AuditEvent
from app.services.core import serialize, serialize_platform, _platform_data_dict
from app.services.security import can_access_record


def quote_detail_relations(db, record, item_id, actor):
    linked = {}
    # Detail-page related lists are scoped to this quote, this organization and
    # the requesting user's permissions. Do not expose cross-tenant linked IDs.
    for key, model in (("notes", Note), ("attachments", Attachment), ("emails", Email)):
        query = select(model).where(
            model.organization_id == record.organization_id,
            model.related_type == "quotes",
            model.related_id == item_id,
            model.archived == False,
        ).order_by(model.created_at.desc()).limit(100)
        linked[key] = [serialize(row, db, actor) for row in db.scalars(query).all()
                       if can_access_record(db, key, row, actor)]
    order_rows = db.scalars(select(PlatformRecord).where(
        PlatformRecord.organization_id == record.organization_id,
        PlatformRecord.resource == "sales_orders",
        PlatformRecord.archived == False,
    ).order_by(PlatformRecord.created_at.desc())).all()
    visible_orders = [row for row in order_rows
                      if str(_platform_data_dict(row).get("quote_id") or "") == str(item_id)
                      and can_access_record(db, "sales_orders", row, actor)]
    linked["sales_orders"] = [serialize_platform(row, db, actor) for row in visible_orders]
    order_ids = {row.id for row in visible_orders}
    invoice_rows = db.scalars(select(PlatformRecord).where(
        PlatformRecord.organization_id == record.organization_id,
        PlatformRecord.resource == "invoices",
        PlatformRecord.archived == False,
    ).order_by(PlatformRecord.created_at.desc())).all()
    linked["invoices"] = [serialize_platform(row, db, actor) for row in invoice_rows
                          if can_access_record(db, "invoices", row, actor) and
                          ((row.related_type == "quotes" and row.related_id == item_id)
                           or _platform_data_dict(row).get("sales_order_id") in order_ids)]
    audit_rows = db.scalars(select(AuditEvent).where(
        AuditEvent.organization_id == record.organization_id,
        AuditEvent.resource == "quotes",
        AuditEvent.record_id == item_id,
    ).order_by(AuditEvent.occurred_at.desc()).limit(100)).all()
    linked["timeline"] = [
        {"id": row.id, "action": row.action, "title": row.summary or "Quote updated",
         "occurred_at": row.occurred_at.isoformat()}
        for row in audit_rows
    ]
    return linked
