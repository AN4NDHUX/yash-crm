from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any, Generator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.models import *

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}

def database_connection() -> tuple[str, dict[str, Any]]:
    raw = os.getenv("DATABASE_URL", "sqlite:///./yashcrm.db").strip()
    # Common managed PostgreSQL providers still emit the legacy postgres:// scheme.
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    if raw.startswith("mysql://"):
        raw = raw.replace("mysql://", "mysql+pymysql://", 1)
    if IS_PRODUCTION and not raw.startswith("postgresql+psycopg://"):
        raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")
    if raw.startswith("sqlite"):
        if IS_PRODUCTION and not env_bool("ALLOW_SQLITE_IN_PRODUCTION"):
            raise RuntimeError("Production requires PostgreSQL/MySQL DATABASE_URL; SQLite is disabled by default.")
        return raw, {"check_same_thread": False}
    parts = urlsplit(raw)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if parts.scheme.startswith("mysql"):
        had_ssl_flag = any(key.lower() == "ssl" for key, _ in query)
        filtered_query = [(key, value) for key, value in query if key.lower() != "ssl"]
        normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(filtered_query), parts.fragment))
        return normalized, ({"ssl": {"verify_mode": "none"}} if had_ssl_flag else {})
    return raw, {}


DB_URL, DB_CONNECT_ARGS = database_connection()
engine_options: dict[str, Any] = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
    "connect_args": DB_CONNECT_ARGS,
}
if not DB_URL.startswith("sqlite"):
    engine_options.update(pool_size=int(os.getenv("DB_POOL_SIZE", "5")), max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")))
engine = create_engine(DB_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


TENANT_ACTOR_ID: ContextVar[int | None] = ContextVar("yashcrm_tenant_actor_id", default=None)
TENANT_ORGANIZATION_ID: ContextVar[int | None] = ContextVar("yashcrm_tenant_organization_id", default=None)


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_scope(execute_state: Any) -> None:
    """Scope organization-aware ORM reads and bulk mutations to the active tenant.

    Record ownership remains a permission concept; organization_id is the tenant
    boundary. Applying the same criteria to ORM SELECT/UPDATE/DELETE statements
    prevents future bulk mutations from crossing organization boundaries.
    """
    organization_id = TENANT_ORGANIZATION_ID.get()
    if not organization_id or not (
        execute_state.is_select or execute_state.is_update or execute_state.is_delete
    ):
        return
    statement = execute_state.statement
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if model in {Organization, OrganizationMember, OrganizationSubscription, OrganizationInvitation, SubscriptionChangeRequest}:
            continue
        if not hasattr(model, "organization_id"):
            continue
        statement = statement.options(
            with_loader_criteria(model, lambda cls: cls.organization_id == organization_id, include_aliases=True)
        )
    execute_state.statement = statement


@event.listens_for(Session, "before_flush")
def _stamp_tenant_organization(session: Session, flush_context: Any, instances: Any) -> None:
    organization_id = TENANT_ORGANIZATION_ID.get()
    if not organization_id:
        return
    for item in session.new:
        if hasattr(item, "organization_id") and getattr(item, "organization_id", None) is None:
            setattr(item, "organization_id", organization_id)


def ensure_additive_schema() -> None:
    # Keep a small additive compatibility layer for databases that may have
    # skipped an older migration. Alembic remains the primary schema manager.
    inspector = inspect(engine)
    if "notifications" not in inspector.get_table_names():
        Notification.__table__.create(bind=engine, checkfirst=True)

    additions = {
        "leads": {
            "archived": "BOOLEAN NOT NULL DEFAULT 0",
            "converted_account_id": "INTEGER NULL",
            "converted_contact_id": "INTEGER NULL",
            "converted_deal_id": "INTEGER NULL",
        },
        "accounts": {"archived": "BOOLEAN NOT NULL DEFAULT 0"},
        "contacts": {"archived": "BOOLEAN NOT NULL DEFAULT 0"},
        "deals": {"archived": "BOOLEAN NOT NULL DEFAULT 0"},
        "activities": {"start_at": "DATETIME NULL", "archived": "BOOLEAN NOT NULL DEFAULT 0"},
        "blueprints": {"transition_requirements": "JSON"},
        "users": {
            "password_hash": "VARCHAR(255) NULL",
            "password_changed_at": "DATETIME NULL",
            "username": "VARCHAR(80) NULL",
            "phone": "VARCHAR(40) NULL",
        },
        "metadata_modules": {
            "owner_id": "INTEGER NULL",
        },
        "organization_settings": {
            "owner_id": "INTEGER NULL",
        },
        "notifications": {
            "user_id": "INTEGER NULL",
            "kind": "VARCHAR(40) NOT NULL DEFAULT 'info'",
            "title": "VARCHAR(220) NOT NULL DEFAULT 'Notification'",
            "body": "TEXT NULL",
            "resource": "VARCHAR(80) NULL",
            "record_id": "INTEGER NULL",
            "read_at": "DATETIME NULL",
            "created_at": "DATETIME NULL",
        },
    }
    inspector = inspect(engine)
    for table, columns in additions.items():
        if table not in inspector.get_table_names():
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column, definition in columns.items():
            if column not in existing:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Never return a poisoned SQLAlchemy session to the pool and never leave a
        # partially flushed request transaction pending after an API failure.
        db.rollback()
        raise
    finally:
        db.close()
