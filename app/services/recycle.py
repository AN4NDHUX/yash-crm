"""Shared recycle-bin record lookup with explicit organization and archival checks."""
from __future__ import annotations

from typing import Any
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlatformRecord


def recycled_rows(
    db: Session,
    resource: str,
    ids: list[int],
    organization_id: int,
    platform_resources: Any,
    resource_map: dict[str, Any],
) -> list[Any]:
    if resource in platform_resources:
        query = select(PlatformRecord).where(
            PlatformRecord.resource == resource,
            PlatformRecord.id.in_(ids),
            PlatformRecord.organization_id == organization_id,
            PlatformRecord.archived == True,
        )
    elif resource in resource_map and resource != "users":
        model = resource_map[resource]
        if not hasattr(model, "archived") or not hasattr(model, "organization_id"):
            raise HTTPException(422, "Module does not support recycle-bin operations")
        query = select(model).where(
            model.id.in_(ids),
            model.organization_id == organization_id,
            model.archived == True,
        )
    else:
        raise HTTPException(404, "Module not found")
    records = db.scalars(query).all()
    if len(records) != len(ids):
        raise HTTPException(404, "One or more deleted records were not found")
    return records
