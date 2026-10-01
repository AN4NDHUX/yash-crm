from __future__ import annotations

import json
import os
import secrets
import base64
import binascii
import csv
import io
import threading
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from email.utils import parseaddr

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    JSON as SAJSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    inspect,
    String,
    Text,
    create_engine,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.platform_catalog import PLATFORM_RESOURCES, SETUP_NAVIGATION, public_catalog


ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = ROOT / "uploads"
DOCUMENT_UPLOAD_ROOT = UPLOAD_ROOT / "documents"
LEAD_CONVERSION_LOCK = threading.Lock()


class ReadinessTrustedHostMiddleware(TrustedHostMiddleware):
    """Allow Railway's internal readiness probe without relaxing other routes."""

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope["type"] == "http"
            and scope.get("method") == "GET"
            and scope.get("path") == "/ready"
        ):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True)
    role: Mapped[str] = mapped_column(String(80), default="Sales rep")
    status: Mapped[str] = mapped_column(String(30), default="Active")
    last_active: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    company: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="New")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    next_follow_up: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(SAJSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    converted_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    converted_contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    converted_deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id"), nullable=True)


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    website: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    billing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(SAJSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(SAJSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Deal(TimestampMixin, Base):
    __tablename__ = "deals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    stage: Mapped[str] = mapped_column(String(80), default="Qualification")
    probability: Mapped[int] = mapped_column(Integer, default=20)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="Active")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Note(TimestampMixin, Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    file_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_size: Mapped[str | None] = mapped_column(String(40), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Email(TimestampMixin, Base):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(220))
    from_email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    to_email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Sent")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(30), default="Task")
    subject: Mapped[str] = mapped_column(String(180))
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Open")
    priority: Mapped[str] = mapped_column(String(30), default="Normal")
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class OrganizationSetting(Base):
    __tablename__ = "organization_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    org_name: Mapped[str] = mapped_column(String(160), default="Yash CRM")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    date_format: Mapped[str] = mapped_column(String(30), default="DD MMM YYYY")
    fiscal_year_start: Mapped[str] = mapped_column(String(20), default="April")
    default_pipeline: Mapped[str] = mapped_column(String(80), default="Default sales pipeline")
    notifications: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, default=dict)


class ApprovalProcess(TimestampMixin, Base):
    __tablename__ = "approval_processes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    module: Mapped[str] = mapped_column(String(50), default="Deals")
    trigger: Mapped[str] = mapped_column(String(180), default="Amount is greater than 0")
    approver: Mapped[str] = mapped_column(String(120), default="Sales manager")
    status: Mapped[str] = mapped_column(String(30), default="Active")
    conditions: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)
    steps: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)


class Blueprint(Base):
    __tablename__ = "blueprints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    module: Mapped[str] = mapped_column(String(50), default="Deals")
    entry_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    stages: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)
    transitions: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)
    transition_requirements: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlatformRecord(TimestampMixin, Base):
    """Shared storage engine for configurable CRM modules and setup records.

    Frequently queried relationship, amount and status values are typed columns;
    module-specific values remain in ``data`` so custom fields do not require a
    schema migration for every configuration change.
    """

    __tablename__ = "platform_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    status: Mapped[str] = mapped_column(String(40), default="Active", index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id"), nullable=True, index=True)
    related_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    resource: Mapped[str] = mapped_column(String(80), index=True)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(String(300))
    before: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, nullable=True)


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource: Mapped[str] = mapped_column(String(80), index=True)
    filename: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(40), default="Completed")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)


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


def ensure_additive_schema() -> None:
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


class RecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    status: str | None = None
    owner_id: int | None = None
    lead_score: int | None = None
    next_follow_up: date | None = None
    notes: str | None = None
    tags: list[str] | None = None
    first_name: str | None = None
    last_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    account_id: int | None = None
    contact_id: int | None = None
    website: str | None = None
    industry: str | None = None
    employees: int | None = None
    annual_revenue: float | None = None
    type: str | None = None
    billing_city: str | None = None
    billing_country: str | None = None
    amount: float | None = None
    stage: str | None = None
    probability: int | None = None
    expected_close_date: date | None = None
    activity_type: str | None = None
    subject: str | None = None
    title: str | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    priority: str | None = None
    related_type: str | None = None
    related_id: int | list[int] | None = None
    description: str | None = None
    content: str | None = None
    completed_at: datetime | None = None
    role: str | None = None
    last_active: datetime | None = None
    module: str | None = None
    trigger: str | None = None
    approver: str | None = None
    conditions: list[dict[str, Any]] | None = None
    steps: list[dict[str, Any]] | None = None
    entry_criteria: str | None = None
    stages: list[dict[str, Any]] | None = None
    transitions: list[dict[str, Any]] | None = None
    transition_requirements: list[dict[str, Any]] | None = None
    active: bool | None = None
    create_deal: bool | None = None
    account_name: str | None = None
    deal_name: str | None = None
    deal_amount: float | None = None
    sku: str | None = None
    category: str | None = None
    unit_price: float | None = None
    stock_quantity: int | None = None
    file_type: str | None = None
    file_size: str | None = None
    url: str | None = None
    from_email: str | None = None
    to_email: str | None = None
    sent_at: datetime | None = None


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_name: str | None = None
    timezone: str | None = None
    currency: str | None = None
    date_format: str | None = None
    fiscal_year_start: str | None = None
    default_pipeline: str | None = None
    notifications: dict[str, bool] | None = None
    name: str | None = None
    email: str | None = None


class BulkArchivePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    related_id: list[int]


class PlatformPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    title: str | None = None
    status: str | None = None
    owner_id: int | None = None
    account_id: int | None = None
    contact_id: int | None = None
    deal_id: int | None = None
    related_type: str | None = None
    related_id: int | None = None
    amount: float | None = None
    due_date: date | None = None


class RestorePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource: str
    record_id: int


RESOURCE_MAP: dict[str, type[Base]] = {
    "leads": Lead,
    "contacts": Contact,
    "accounts": Account,
    "deals": Deal,
    "products": Product,
    "notes": Note,
    "attachments": Attachment,
    "emails": Email,
    "activities": Activity,
    "users": User,
    "approval_processes": ApprovalProcess,
    "blueprints": Blueprint,
}
SEARCH_COLUMNS: dict[str, list[str]] = {
    "leads": ["name", "company", "email", "source", "status"],
    "contacts": ["first_name", "last_name", "email", "job_title"],
    "accounts": ["name", "website", "industry", "billing_city"],
    "deals": ["name", "stage", "source", "status"],
    "products": ["name", "sku", "category", "status"],
    "notes": ["title", "content"],
    "attachments": ["name", "file_type"],
    "emails": ["subject", "from_email", "to_email", "status"],
    "activities": ["subject", "activity_type", "status", "related_type"],
    "users": ["name", "email", "role", "status"],
    "approval_processes": ["name", "module", "trigger", "approver", "status"],
    "blueprints": ["name", "module", "entry_criteria"],
}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_date_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (date, datetime)):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_datetime_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))


def coerce_value(model: type[Base], key: str, value: Any) -> Any:
    column = model.__table__.columns.get(key)
    if column is None:
        return value
    if isinstance(column.type, DateTime):
        return parse_datetime_value(value)
    if isinstance(column.type, Date):
        return parse_date_value(value)
    if isinstance(column.type, Integer) and value not in (None, ""):
        return int(value)
    if isinstance(column.type, Float) and value not in (None, ""):
        return float(value)
    if isinstance(column.type, Boolean) and isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "on"}
    if isinstance(column.type, SAJSON) and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [part.strip() for part in value.split(",") if part.strip()]
    return value


def serialize(obj: Any, db: Session | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        data[column.name] = value
    if db is not None and hasattr(obj, "owner_id") and obj.owner_id:
        owner = db.get(User, obj.owner_id)
        data["owner_name"] = owner.name if owner else "Unassigned"
    if isinstance(obj, Contact):
        data["full_name"] = f"{obj.first_name} {obj.last_name}".strip()
    if isinstance(obj, Activity) and obj.related_type and obj.related_id:
        data["related_label"] = related_label(db, obj.related_type, obj.related_id) if db else None
    return data


def related_label(db: Session, related_type: str, related_id: int) -> str | None:
    model = RESOURCE_MAP.get(f"{related_type.lower()}s") or RESOURCE_MAP.get(related_type.lower())
    if model is None:
        return None
    item = db.get(model, related_id)
    if item is None:
        return None
    if isinstance(item, Contact):
        return f"{item.first_name} {item.last_name}".strip()
    return getattr(item, "name", getattr(item, "subject", f"{related_type} #{related_id}"))


def platform_config(resource: str) -> dict[str, Any]:
    config = PLATFORM_RESOURCES.get(resource)
    if config is None:
        raise HTTPException(404, "Unknown Yash CRM module or setup resource")
    return config


def platform_values(payload: PlatformPayload) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


def validate_platform_values(resource: str, values: dict[str, Any], *, partial: bool = False) -> None:
    config = platform_config(resource)
    field_map = {item["key"]: item for item in config.get("fields", [])}
    if not partial:
        for item in config.get("fields", []):
            if item.get("required") and values.get(item["key"]) in (None, "", []):
                raise HTTPException(422, f"{item['label']} is required")
    for key in values:
        if key not in field_map and key not in {"title", "owner_id", "account_id", "contact_id", "deal_id", "related_type", "related_id", "amount", "due_date", "status", "file_name", "file_size", "content_type", "paid_amount", "balance_due"}:
            raise HTTPException(422, f"Unknown field '{key}' for {config['label']}")
    for item in config.get("fields", []):
        if item.get("type") == "json" and item["key"] in values and values[item["key"]] is not None and not isinstance(values[item["key"]], (dict, list)):
            raise HTTPException(422, f"{item['label']} must be valid JSON")
        if item.get("options") and values.get(item["key"]) not in (None, "") and str(values[item["key"]]) not in item["options"]:
            raise HTTPException(422, f"{item['label']} has an unsupported value")


def sync_platform_columns(record: PlatformRecord, values: dict[str, Any]) -> None:
    record.title = str(values.get("name") or values.get("title") or record.title or "Untitled").strip()
    record.status = str(values.get("status") or record.status or "Active")
    for key in ("owner_id", "account_id", "contact_id", "deal_id", "related_type", "related_id", "amount", "due_date"):
        if key in values:
            value = values[key]
            if key == "due_date" and isinstance(value, str) and value:
                value = date.fromisoformat(value[:10])
            setattr(record, key, value)
    record.data = json_safe(values)


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def get_platform_reference(db: Session, resource: str, raw_id: Any, label: str) -> PlatformRecord:
    try:
        item_id = int(raw_id)
    except (TypeError, ValueError) as error:
        raise HTTPException(422, f"Select a valid {label.lower()}") from error
    record = db.scalar(select(PlatformRecord).where(
        PlatformRecord.resource == resource,
        PlatformRecord.id == item_id,
        PlatformRecord.archived == False,
    ))
    if record is None:
        raise HTTPException(422, f"The selected {label.lower()} no longer exists")
    return record


def normalize_platform_links(db: Session, resource: str, values: dict[str, Any]) -> None:
    """Validate cross-module links and inherit shared customer/revenue context."""
    parent: PlatformRecord | None = None
    if resource == "quotes" and values.get("deal_id"):
        deal = db.get(Deal, int(values["deal_id"]))
        if deal is None or deal.archived:
            raise HTTPException(422, "The selected opportunity no longer exists")
        if values.get("account_id") in (None, ""):
            values["account_id"] = deal.account_id
        if values.get("contact_id") in (None, ""):
            values["contact_id"] = deal.contact_id
        if values.get("owner_id") in (None, ""):
            values["owner_id"] = deal.owner_id
        if values.get("amount") in (None, ""):
            values["amount"] = deal.amount
        values.update({"related_type": "deals", "related_id": deal.id})
    elif resource == "sales_orders" and values.get("quote_id"):
        parent = get_platform_reference(db, "quotes", values["quote_id"], "Quote")
    elif resource == "purchase_orders" and values.get("vendor_id"):
        parent = get_platform_reference(db, "vendors", values["vendor_id"], "Vendor")
    elif resource == "invoices" and values.get("sales_order_id"):
        parent = get_platform_reference(db, "sales_orders", values["sales_order_id"], "Sales order")
    elif resource == "payments" and values.get("invoice_id"):
        parent = get_platform_reference(db, "invoices", values["invoice_id"], "Invoice")
    elif resource == "site_visits" and values.get("lead_id"):
        lead = db.get(Lead, int(values["lead_id"]))
        if lead is None or lead.archived:
            raise HTTPException(422, "The selected lead no longer exists")
        if values.get("owner_id") in (None, ""):
            values["owner_id"] = lead.owner_id
        values.update({"related_type": "leads", "related_id": lead.id})

    if parent is not None:
        inherited = dict(parent.data or {})
        for key in ("owner_id", "account_id", "contact_id", "deal_id"):
            if values.get(key) in (None, "") and getattr(parent, key, None) is not None:
                values[key] = getattr(parent, key)
        if values.get("amount") in (None, "") and parent.amount is not None:
            values["amount"] = parent.amount
        values.update({"related_type": parent.resource, "related_id": parent.id})


TRANSACTION_NUMBERS = {
    "quotes": ("quote_number", "QUO"),
    "sales_orders": ("order_number", "SO"),
    "purchase_orders": ("po_number", "PO"),
    "invoices": ("invoice_number", "INV"),
}


def ensure_transaction_number(record: PlatformRecord) -> None:
    definition = TRANSACTION_NUMBERS.get(record.resource)
    if not definition:
        return
    key, prefix = definition
    values = dict(record.data or {})
    if not values.get(key):
        values[key] = f"{prefix}-{datetime.utcnow():%Y%m}-{record.id:05d}"
        sync_platform_columns(record, values)


def refresh_invoice_balance(db: Session, invoice_id: int) -> None:
    invoice = db.scalar(select(PlatformRecord).where(
        PlatformRecord.resource == "invoices", PlatformRecord.id == invoice_id,
        PlatformRecord.archived == False,
    ))
    if invoice is None:
        return
    payments = db.scalars(select(PlatformRecord).where(
        PlatformRecord.resource == "payments", PlatformRecord.archived == False,
    )).all()
    paid = sum(float(item.amount or 0) for item in payments if int((item.data or {}).get("invoice_id") or 0) == invoice_id and item.status in {"Received", "Cleared"})
    total = float(invoice.amount or 0)
    values = dict(invoice.data or {})
    values["paid_amount"] = paid
    values["balance_due"] = max(total - paid, 0)
    if paid >= total and total > 0:
        values["status"] = "Paid"
    elif paid > 0:
        values["status"] = "Partially Paid"
    sync_platform_columns(invoice, values)


def serialize_platform(record: PlatformRecord, db: Session | None = None) -> dict[str, Any]:
    data = dict(record.data or {})
    data.update({
        "id": record.id,
        "resource": record.resource,
        "name": record.title,
        "title": record.title,
        "status": record.status,
        "owner_id": record.owner_id,
        "account_id": record.account_id,
        "contact_id": record.contact_id,
        "deal_id": record.deal_id,
        "related_type": record.related_type,
        "related_id": record.related_id,
        "amount": record.amount,
        "due_date": record.due_date.isoformat() if record.due_date else None,
        "archived": record.archived,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    })
    if db and record.owner_id:
        owner = db.get(User, record.owner_id)
        data["owner_name"] = owner.name if owner else None
    return data


def add_audit(db: Session, action: str, resource: str, record_id: int | None,
              summary: str, before: dict[str, Any] | None = None,
              after: dict[str, Any] | None = None, actor_id: int | None = None) -> None:
    db.add(AuditEvent(actor_id=actor_id, action=action, resource=resource, record_id=record_id,
                      summary=summary[:300], before=before, after=after))


def run_platform_automation(db: Session, resource: str, event: str,
                            record: PlatformRecord, values: dict[str, Any]) -> None:
    """Execute deterministic local automation and queue external work via audit events.

    No outbound network call is made in the web request. Webhook and schedule
    delivery is deliberately represented as queued work for a production worker.
    """
    rules = db.scalars(select(PlatformRecord).where(
        PlatformRecord.resource == "workflow_rules", PlatformRecord.archived == False,
        PlatformRecord.status == "Active"
    )).all()
    for rule in rules:
        config = rule.data or {}
        if str(config.get("module", "")).lower().replace(" ", "_") not in {resource, "all", "*"}:
            continue
        if config.get("event") not in (None, "", event):
            continue
        criterion = config.get("criteria_field")
        if criterion and str(values.get(criterion, "")) != str(config.get("criteria_value", "")):
            continue
        action = config.get("action_type") or "audit"
        if action == "field_update" and config.get("action_value"):
            try:
                field_name, field_value = str(config["action_value"]).split("=", 1)
                changed = dict(record.data or {})
                changed[field_name.strip()] = field_value.strip()
                sync_platform_columns(record, changed)
            except ValueError:
                add_audit(db, "automation_error", resource, record.id, f"Workflow {rule.title} has an invalid field update")
                continue
        elif action == "create_task":
            owner_id = record.owner_id or db.scalar(select(User.id).where(User.status == "Active").order_by(User.id))
            db.add(Activity(activity_type="Task", subject=str(config.get("action_value") or f"Follow up: {record.title}"), owner_id=owner_id, status="Open", priority="Normal", related_type=resource, related_id=record.id))
        add_audit(db, "automation", resource, record.id, f"Workflow '{rule.title}' executed action '{action}'")


def apply_assignment_rule(db: Session, resource: str, values: dict[str, Any]) -> None:
    if values.get("owner_id"):
        return
    rules = db.scalars(select(PlatformRecord).where(
        PlatformRecord.resource == "assignment_rules", PlatformRecord.archived == False,
        PlatformRecord.status == "Active"
    ).order_by(PlatformRecord.id)).all()
    for rule in rules:
        config = rule.data or {}
        if str(config.get("module", "")).lower().replace(" ", "_") != resource:
            continue
        criterion = config.get("criteria_field")
        if criterion and str(values.get(criterion, "")) != str(config.get("criteria_value", "")):
            continue
        if config.get("owner_id"):
            values["owner_id"] = int(config["owner_id"])
            return


def seed_defaults(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    now = datetime.utcnow()
    maya = User(name="Maya Iyer", email="maya@yashcrm.app", role="Administrator", status="Active", last_active=now)
    arjun = User(name="Arjun Mehta", email="arjun@yashcrm.app", role="Sales manager", status="Active", last_active=now - timedelta(hours=2))
    riya = User(name="Riya Shah", email="riya@yashcrm.app", role="Sales rep", status="Active", last_active=now - timedelta(days=1))
    db.add_all([maya, arjun, riya])
    db.flush()

    acme = Account(name="Acme Retail Group", website="acmeretail.example", phone="+91 80 4000 1222", industry="Retail", employees=420, annual_revenue=28500000, type="Customer", owner_id=arjun.id, billing_city="Bengaluru", billing_country="India", notes="Regional retail group expanding into two new cities.", tags=["priority", "expansion"])
    northstar = Account(name="Northstar Logistics", website="northstar.example", phone="+91 22 4200 9911", industry="Logistics", employees=180, annual_revenue=14200000, type="Prospect", owner_id=riya.id, billing_city="Mumbai", billing_country="India", notes="Evaluating a unified customer operations workspace.", tags=["new"])
    evergreen = Account(name="Evergreen Labs", website="evergreen.example", phone="+91 11 4800 2144", industry="Technology", employees=75, annual_revenue=6900000, type="Partner", owner_id=maya.id, billing_city="New Delhi", billing_country="India", notes="Technology partner for integration opportunities.", tags=["partner"])
    db.add_all([acme, northstar, evergreen])
    db.flush()

    leads = [
        Lead(name="Nikhil Rao", company="Orbit Foods", email="nikhil@orbitfoods.example", phone="+91 98 2200 7711", source="Website", status="Qualified", owner_id=arjun.id, lead_score=82, next_follow_up=date.today() + timedelta(days=2), notes="Strong fit for multi-location rollout.", tags=["hot", "retail"]),
        Lead(name="Sara Thomas", company="Fieldstone Design", email="sara@fieldstone.example", phone="+91 99 1002 1981", source="Referral", status="Contacted", owner_id=riya.id, lead_score=58, next_follow_up=date.today() + timedelta(days=5), notes="Requested a short overview and pricing range.", tags=["design"]),
        Lead(name="Dev Malhotra", company="Kite Health", email="dev@kitehealth.example", phone="+91 97 4400 8812", source="LinkedIn", status="New", owner_id=maya.id, lead_score=41, next_follow_up=date.today() + timedelta(days=1), notes="New inbound lead.", tags=["inbound"]),
        Lead(name="Aanya Kapoor", company="Urban Nest", email="aanya@urbannest.example", phone="+91 98 7112 4400", source="Event", status="Converted", owner_id=arjun.id, lead_score=91, next_follow_up=None, notes="Converted after product workshop.", tags=["converted"]),
    ]
    db.add_all(leads)
    db.flush()

    contacts = [
        Contact(first_name="Priya", last_name="Nair", email="priya@acmeretail.example", phone="+91 98 6011 2244", job_title="Head of Operations", department="Operations", account_id=acme.id, owner_id=arjun.id, notes="Primary business sponsor.", tags=["champion"]),
        Contact(first_name="Kabir", last_name="Joshi", email="kabir@northstar.example", phone="+91 98 2012 4411", job_title="VP Customer Experience", department="Customer Experience", account_id=northstar.id, owner_id=riya.id, notes="Owns the evaluation committee.", tags=["evaluation"]),
        Contact(first_name="Meera", last_name="Sethi", email="meera@evergreen.example", phone="+91 99 2100 1893", job_title="Partnerships Lead", department="Partnerships", account_id=evergreen.id, owner_id=maya.id, notes="Integration partner contact.", tags=["partner"]),
    ]
    db.add_all(contacts)
    db.flush()

    deals = [
        Deal(name="Acme CX rollout", account_id=acme.id, contact_id=contacts[0].id, amount=480000, stage="Proposal", probability=60, expected_close_date=date.today() + timedelta(days=24), owner_id=arjun.id, type="New business", source="Website", status="Open", notes="Proposal review scheduled next week."),
        Deal(name="Northstar service desk", account_id=northstar.id, contact_id=contacts[1].id, amount=275000, stage="Needs Analysis", probability=35, expected_close_date=date.today() + timedelta(days=48), owner_id=riya.id, type="New business", source="Referral", status="Open", notes="Discovery workshop in progress."),
        Deal(name="Evergreen integration", account_id=evergreen.id, contact_id=contacts[2].id, amount=125000, stage="Negotiation", probability=78, expected_close_date=date.today() + timedelta(days=11), owner_id=maya.id, type="Partnership", source="Partner", status="Open", notes="Commercial terms under review."),
        Deal(name="Urban Nest pilot", account_id=acme.id, contact_id=contacts[0].id, amount=95000, stage="Closed Won", probability=100, expected_close_date=date.today() - timedelta(days=4), owner_id=arjun.id, type="Expansion", source="Event", status="Won", notes="Pilot converted to annual contract."),
    ]
    db.add_all(deals)
    db.flush()

    activities = [
        Activity(activity_type="Meeting", subject="Proposal review with Acme", due_at=datetime.utcnow() + timedelta(days=2, hours=3), owner_id=arjun.id, status="Open", priority="High", related_type="accounts", related_id=acme.id, description="Review the proposal and implementation timeline."),
        Activity(activity_type="Call", subject="Discovery follow-up with Northstar", due_at=datetime.utcnow() + timedelta(days=1, hours=2), owner_id=riya.id, status="Open", priority="Normal", related_type="deals", related_id=deals[1].id, description="Confirm decision criteria and stakeholders."),
        Activity(activity_type="Task", subject="Send integration checklist", due_at=datetime.utcnow() - timedelta(hours=4), owner_id=maya.id, status="Open", priority="High", related_type="contacts", related_id=contacts[2].id, description="Share the current API checklist."),
        Activity(activity_type="Call", subject="Welcome call completed", due_at=datetime.utcnow() - timedelta(days=1), owner_id=arjun.id, status="Completed", priority="Normal", related_type="leads", related_id=leads[3].id, description="Introductory call completed.", completed_at=datetime.utcnow() - timedelta(days=1)),
    ]
    db.add_all(activities)
    db.add(OrganizationSetting(id=1, org_name="Yash CRM", timezone="Asia/Kolkata", currency="INR", date_format="DD MMM YYYY", fiscal_year_start="April", default_pipeline="Default sales pipeline", notifications={"daily_digest": True, "mentions": True, "deal_updates": True}))
    db.add(ApprovalProcess(name="Discount approval", module="Deals", trigger="Discount is greater than 15%", approver="Sales manager", status="Active", conditions=[{"field": "discount", "operator": ">", "value": "15"}], steps=[{"order": 1, "approver": "Sales manager"}]))
    db.add(Blueprint(name="Deal progression", module="Deals", entry_criteria="Amount is greater than 0", stages=[{"id": "qualification", "label": "Qualification"}, {"id": "needs-analysis", "label": "Needs Analysis"}, {"id": "proposal", "label": "Proposal"}, {"id": "negotiation", "label": "Negotiation"}, {"id": "closed-won", "label": "Closed Won"}], transitions=[{"from": "Qualification", "to": "Needs Analysis", "label": "Qualify"}, {"from": "Needs Analysis", "to": "Proposal", "label": "Create proposal"}, {"from": "Proposal", "to": "Negotiation", "label": "Start negotiation"}, {"from": "Negotiation", "to": "Closed Won", "label": "Close won"}], active=True))
    db.commit()


def ensure_workspace_defaults(db: Session) -> None:
    if db.get(OrganizationSetting, 1) is None:
        db.add(OrganizationSetting(id=1, org_name="Yash CRM", timezone="Asia/Kolkata", currency="INR", date_format="DD MMM YYYY", fiscal_year_start="April", default_pipeline="Default sales pipeline", notifications={"daily_digest": True, "mentions": True, "deal_updates": True}))
    if db.scalar(select(ApprovalProcess.id).limit(1)) is None:
        db.add(ApprovalProcess(name="Discount approval", module="Deals", trigger="Discount is greater than 15%", approver="Sales manager", status="Active", conditions=[{"field": "discount", "operator": ">", "value": "15"}], steps=[{"order": 1, "approver": "Sales manager"}]))
    if db.scalar(select(Blueprint.id).limit(1)) is None:
        db.add(Blueprint(name="Deal progression", module="Deals", entry_criteria="Amount is greater than 0", stages=[{"id": "qualification", "label": "Qualification"}], transitions=[], transition_requirements=[], active=True))
    maya = db.scalar(select(User).order_by(User.id).limit(1))
    account = db.scalar(select(Account).order_by(Account.id).limit(1))
    contact = db.scalar(select(Contact).order_by(Contact.id).limit(1))
    lead = db.scalar(select(Lead).order_by(Lead.id).limit(1))
    if db.scalar(select(Product.id).limit(1)) is None and maya:
        db.add_all([
            Product(name="Yash CRM Enterprise", sku="YCR-ENT-001", category="CRM platform", unit_price=480000, stock_quantity=999, status="Active", description="Enterprise customer operations workspace.", owner_id=maya.id, related_type="accounts" if account else None, related_id=account.id if account else None),
            Product(name="Implementation Sprint", sku="YCR-SVC-010", category="Professional services", unit_price=125000, stock_quantity=20, status="Active", description="Guided onboarding and rollout package.", owner_id=maya.id, related_type="contacts" if contact else None, related_id=contact.id if contact else None),
        ])
    if db.scalar(select(Note.id).limit(1)) is None and maya and (account or lead):
        db.add(Note(title="Discovery notes", content="Capture the next stakeholder discussion and rollout priorities.", related_type="accounts" if account else "leads", related_id=account.id if account else lead.id, owner_id=maya.id))
    if db.scalar(select(Attachment.id).limit(1)) is None and maya and account:
        db.add(Attachment(name="Customer requirements.pdf", file_type="PDF", file_size="2.4 MB", url="#", related_type="accounts", related_id=account.id, owner_id=maya.id))
    if db.scalar(select(Email.id).limit(1)) is None and maya and contact:
        db.add(Email(subject="Follow-up and next steps", from_email="maya@yashcrm.app", to_email=contact.email, body="Sharing the next steps from our conversation.", status="Sent", sent_at=datetime.utcnow() - timedelta(hours=3), related_type="contacts", related_id=contact.id, owner_id=maya.id))
    db.commit()


def ensure_platform_defaults(db: Session, include_demo: bool = False) -> None:
    admin = db.scalar(select(User).order_by(User.id))
    defaults: dict[str, list[dict[str, Any]]] = {
        "company_details": [{"name": "Yash CRM", "legal_name": "Yash CRM", "email": admin.email if admin else "admin@yashcrm.local", "status": "Active"}],
        "fiscal_years": [{"name": "April - March", "start_date": "2026-04-01", "end_date": "2027-03-31", "status": "Active"}],
        "roles": [{"name": "Administrator", "data_scope": "All", "status": "Active", "description": "Full record visibility."}, {"name": "Sales Manager", "parent_role": "Administrator", "data_scope": "Own and Subordinates", "status": "Active"}, {"name": "Sales Representative", "parent_role": "Sales Manager", "data_scope": "Own", "status": "Active"}],
        "profiles": [{"name": "Administrator", "permissions": {"all_modules": ["create", "read", "update", "delete", "export"], "setup": ["manage"]}, "status": "Active"}, {"name": "Standard", "permissions": {"crm_modules": ["create", "read", "update"], "setup": []}, "status": "Active"}],
        "permissions": [{"name": "CRM administrator", "module": "*", "grants": ["create", "read", "update", "delete", "export", "manage_setup"], "status": "Active"}],
        "pipelines": [{"name": "Default sales pipeline", "module": "Deals", "stages": [{"name": "Qualification", "probability": 20}, {"name": "Needs Analysis", "probability": 35}, {"name": "Proposal", "probability": 55}, {"name": "Negotiation", "probability": 75}, {"name": "Closed Won", "probability": 100, "closed": True}, {"name": "Closed Lost", "probability": 0, "closed": True}], "status": "Active"}],
        "custom_views": [{"name": "My open records", "module": "Deals", "filters": [{"field": "status", "operator": "equals", "value": "Open"}], "sort": "updated_desc", "columns": ["name", "account", "amount", "stage", "owner"], "status": "Active"}],
        "email_templates": [{"name": "Sales follow-up", "subject": "Next steps for {{account.name}}", "module": "Deals", "content": "Hello {{contact.first_name}},\n\nThank you for your time. Here are the agreed next steps.", "status": "Active"}],
        "quote_templates": [{"name": "Standard quote", "content": "Quote {{quote.quote_number}}\nCustomer: {{account.name}}\nTotal: {{quote.amount}}", "status": "Active"}],
        "invoice_templates": [{"name": "Standard invoice", "content": "Invoice {{invoice.invoice_number}}\nDue: {{invoice.due_date}}\nTotal: {{invoice.amount}}", "status": "Active"}],
        "api_settings": [{"name": "Local API", "scopes": ["crm.read", "crm.write"], "token_hint": "Generate credentials through your deployment secret manager", "status": "Inactive"}],
    }
    if include_demo:
        defaults.update({
            "price_books": [{"name": "Standard INR", "currency": "INR", "discount_percent": 0, "status": "Active", "description": "Default list pricing."}],
            "vendors": [{"name": "Sample Implementation Partner", "email": "partner@example.com", "category": "Professional services", "status": "Active"}],
            "campaigns": [{"name": "Customer success webinar", "campaign_type": "Webinar", "status": "Planned", "budget": 25000}],
            "cases": [{"name": "Sample onboarding question", "case_number": "CASE-1001", "priority": "Normal", "channel": "Web", "status": "New", "description": "Demonstration case for the local development workspace."}],
            "solutions": [{"name": "Getting started checklist", "category": "Onboarding", "status": "Published", "content": "Confirm owners, import clean data, configure the pipeline, and review permissions."}],
            "forecasts": [{"name": "Current quarter", "period": "Q4 2026", "target": 2500000, "committed": 0, "best_case": 0, "status": "Open"}],
            "reports": [{"name": "Open pipeline by stage", "module": "Deals", "report_type": "Summary", "filters": [{"field": "status", "value": "Open"}], "columns": ["stage", "count", "amount"], "status": "Active"}],
            "dashboards": [{"name": "Sales overview", "audience": "Sales team", "components": [{"type": "metric", "source": "open_deals"}, {"type": "pipeline", "source": "deals_by_stage"}], "status": "Active"}],
        })
    for resource, rows in defaults.items():
        if db.scalar(select(func.count()).select_from(PlatformRecord).where(PlatformRecord.resource == resource)):
            continue
        for values in rows:
            record = PlatformRecord(resource=resource, title=str(values.get("name") or "Untitled"), data={})
            sync_platform_columns(record, values)
            db.add(record)
    db.commit()


STAGE_PROBABILITY = {"Qualification": 20, "Needs Analysis": 40, "Proposal": 60, "Negotiation": 80, "Closed Won": 100, "Closed Lost": 0}
STAGE_STATUS = {"Closed Won": "Won", "Closed Lost": "Lost"}


def order_clauses(model: type[Base], sort: str) -> list[Any]:
    created = getattr(model, "created_at", model.id)
    if sort == "name_asc":
        for attrs in (("last_name", "first_name"), ("name",), ("subject",), ("title",)):
            if all(hasattr(model, attr) for attr in attrs):
                return [getattr(model, attr).asc() for attr in attrs]
        return [model.id.asc()]
    if sort == "amount_desc" and hasattr(model, "amount"):
        return [model.amount.desc()]
    if sort == "close_asc" and hasattr(model, "expected_close_date"):
        return [model.expected_close_date.asc()]
    if sort == "score_desc" and hasattr(model, "lead_score"):
        return [model.lead_score.desc()]
    return [created.desc(), model.id.desc()]


def list_resource(db: Session, resource: str, search: str | None, status: str | None, owner_id: int | None, sort: str, min_amount: float | None, max_amount: float | None, close_from: date | None, close_to: date | None, limit: int, offset: int, activity_type: str | None = None) -> dict[str, Any]:
    model = RESOURCE_MAP[resource]
    query = select(model)
    if hasattr(model, "archived"):
        query = query.where(getattr(model, "archived") == False)
    if search:
        clauses = [getattr(model, column).ilike(f"%{search}%") for column in SEARCH_COLUMNS.get(resource, []) if hasattr(model, column)]
        if resource == "contacts":
            clauses.append((Contact.first_name + " " + Contact.last_name).ilike(f"%{search}%"))
        if clauses:
            query = query.where(or_(*clauses))
    if status:
        if resource == "deals" and status in STAGE_PROBABILITY:
            query = query.where(Deal.stage == status)
        elif hasattr(model, "status"):
            query = query.where(getattr(model, "status") == status)
        elif hasattr(model, "stage"):
            query = query.where(getattr(model, "stage") == status)
    if owner_id and hasattr(model, "owner_id"):
        query = query.where(getattr(model, "owner_id") == owner_id)
    if resource == "activities" and activity_type:
        query = query.where(Activity.activity_type == activity_type)
    if resource == "deals":
        if min_amount is not None:
            query = query.where(Deal.amount >= min_amount)
        if max_amount is not None:
            query = query.where(Deal.amount <= max_amount)
        if close_from:
            query = query.where(Deal.expected_close_date >= close_from)
        if close_to:
            query = query.where(Deal.expected_close_date <= close_to)
    count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(*order_clauses(model, sort)).offset(offset).limit(limit)).all()
    return {"items": [serialize(row, db) for row in rows], "total": count, "limit": limit, "offset": offset}


def get_or_create_settings(db: Session) -> OrganizationSetting:
    setting = db.get(OrganizationSetting, 1)
    if setting is None:
        setting = OrganizationSetting(id=1, org_name="Yash CRM", timezone="Asia/Kolkata", currency="INR", date_format="DD MMM YYYY", fiscal_year_start="April", default_pipeline="Default sales pipeline", notifications={})
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def ensure_cloud_admin(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    name = os.getenv("ADMIN_NAME", "Administrator").strip() or "Administrator"
    email = os.getenv("ADMIN_EMAIL", "admin@yashcrm.local").strip().lower()
    if parseaddr(email)[1] != email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise RuntimeError("ADMIN_EMAIL must be a valid email address")
    db.add(User(name=name, email=email, role="Administrator", status="Active", last_active=datetime.utcnow()))
    db.commit()


def validate_production_settings() -> None:
    if not IS_PRODUCTION:
        return
    hosts = [value.strip() for value in os.getenv("ALLOWED_HOSTS", "").split(",") if value.strip()]
    if not hosts or "*" in hosts:
        raise RuntimeError("ALLOWED_HOSTS must list the production hostname; wildcard access is not allowed.")
    origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "").split(",") if value.strip()]
    if "*" in origins:
        raise RuntimeError("CORS_ORIGINS cannot contain '*' in production.")
    if not env_bool("ENABLE_AUTH", True):
        raise RuntimeError("ENABLE_AUTH must remain enabled in production.")
    if env_bool("ENABLE_AUTH", True):
        username = os.getenv("APP_USERNAME", "").strip()
        password = os.getenv("APP_PASSWORD", "")
        insecure_passwords = {"change-this-to-a-long-password", "replace-with-at-least-12-random-characters"}
        if not username or len(password) < 12 or password.lower() in insecure_passwords or secrets.compare_digest(username.encode(), password.encode()):
            raise RuntimeError("APP_USERNAME and an APP_PASSWORD of at least 12 characters are required.")
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    if parseaddr(admin_email)[1] != admin_email or "@" not in admin_email or "." not in admin_email.rsplit("@", 1)[-1]:
        raise RuntimeError("ADMIN_EMAIL must be a valid production email address.")


def startup() -> None:
    # Local/desktop mode remains self-initialising. Production schema changes are
    # performed by Alembic before the web process starts (see cloud-entrypoint.sh).
    if not IS_PRODUCTION:
        Base.metadata.create_all(bind=engine)
        ensure_additive_schema()
    with SessionLocal() as db:
        if not IS_PRODUCTION or env_bool("SEED_DEMO_DATA"):
            seed_defaults(db)
        elif IS_PRODUCTION:
            ensure_cloud_admin(db)
        ensure_workspace_defaults(db)
        ensure_platform_defaults(db, include_demo=(not IS_PRODUCTION or env_bool("SEED_DEMO_DATA")))


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production_settings()
    startup()
    yield


app = FastAPI(
    title="Yash CRM",
    version="0.1.0.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

allowed_hosts = [x.strip() for x in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1" if IS_PRODUCTION else "*").split(",") if x.strip()]
app.add_middleware(ReadinessTrustedHostMiddleware, allowed_hosts=allowed_hosts)

allowed_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()]
if allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "Authorization"])

@app.middleware("http")
async def cloud_security(request: Request, call_next):
    # Health probes remain unauthenticated. All user/data surfaces can be protected
    # with HTTP Basic at the app layer; put SSO/OIDC at the proxy when available.
    auth_enabled = env_bool("ENABLE_AUTH", IS_PRODUCTION)
    if auth_enabled and request.url.path not in {"/health", "/ready"}:
        expected_user = os.getenv("APP_USERNAME", "").strip()
        expected_password = os.getenv("APP_PASSWORD", "")
        if not expected_user or len(expected_password) < 12:
            return JSONResponse(status_code=503, content={"detail": "Cloud authentication is not configured safely."})
        header = request.headers.get("Authorization", "")
        valid = False
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                supplied_user, supplied_password = decoded.split(":", 1)
                valid = secrets.compare_digest(supplied_user.encode(), expected_user.encode()) and secrets.compare_digest(supplied_password.encode(), expected_password.encode())
            except (binascii.Error, ValueError, UnicodeDecodeError):
                valid = False
        if not valid:
            response = Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Yash CRM"'})
            return add_security_headers(response, request)
    response = await call_next(request)
    return add_security_headers(response, request)


def add_security_headers(response: Response, request: Request) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, __: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "That value already exists or a required field is missing."})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, error: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": f"Invalid value: {error}"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "yash-crm"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(select(1))
    except Exception as error:
        raise HTTPException(503, f"Database is not ready: {error.__class__.__name__}") from error
    return {"status": "ok", "service": "yash-crm", "database": "ready"}


@app.get("/manus-routes.json")
def route_manifest() -> FileResponse:
    return FileResponse(ROOT / "public" / "manus-routes.json", media_type="application/json")


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(ROOT / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/manifest.webmanifest")
def web_manifest() -> FileResponse:
    return FileResponse(ROOT / "public" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker() -> FileResponse:
    return FileResponse(ROOT / "public" / "sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@app.get("/api/meta")
def meta(db: Session = Depends(get_db)) -> dict[str, Any]:
    users = db.scalars(select(User).where(User.status == "Active").order_by(User.name)).all()
    return {"users": [serialize(user, db) for user in users], "lead_statuses": ["New", "Contacted", "Qualified", "Unqualified", "Converted"], "deal_stages": ["Qualification", "Needs Analysis", "Proposal", "Negotiation", "Closed Won", "Closed Lost"], "activity_types": ["Task", "Call", "Meeting"], "industries": ["Technology", "Retail", "Logistics", "Healthcare", "Finance", "Education", "Other"]}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    closed = ["Closed Won", "Closed Lost"]
    total_leads = db.scalar(select(func.count()).select_from(Lead).where(Lead.archived == False)) or 0
    open_deals = db.scalar(select(func.count()).select_from(Deal).where(Deal.archived == False, Deal.stage.not_in(closed))) or 0
    pipeline_value = db.scalar(select(func.coalesce(func.sum(Deal.amount), 0)).where(Deal.archived == False, Deal.stage.not_in(closed))) or 0
    activities_due = db.scalar(select(func.count()).select_from(Activity).where(Activity.archived == False, Activity.status != "Completed", Activity.due_at <= datetime.utcnow() + timedelta(days=7))) or 0
    stage_rows = db.execute(select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0)).where(Deal.archived == False, Deal.stage.not_in(closed)).group_by(Deal.stage)).all()
    lead_rows = db.execute(select(Lead.status, func.count(Lead.id)).where(Lead.archived == False).group_by(Lead.status)).all()
    recent = db.scalars(select(Activity).where(Activity.archived == False).order_by(Activity.created_at.desc()).limit(6)).all()
    performance = sales_performance(db)
    return {"metrics": {"total_leads": total_leads, "open_deals": open_deals, "pipeline_value": float(pipeline_value or 0), "activities_due": activities_due, "payments_received": performance["totals"]["achieved"], "team_target": performance["totals"]["target"]}, "pipeline": [{"stage": stage, "count": int(count), "amount": float(amount or 0)} for stage, count, amount in stage_rows], "lead_funnel": [{"status": status, "count": int(count)} for status, count in lead_rows], "recent_activity": [serialize(item, db) for item in recent], "sales_performance": performance["people"], "attention": performance["attention"]}


def _date_value(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def sales_performance(db: Session) -> dict[str, Any]:
    today = date.today()
    users = db.scalars(select(User).where(User.status == "Active").order_by(User.name)).all()
    targets = db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "sales_targets", PlatformRecord.archived == False)).all()
    payments = db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "payments", PlatformRecord.archived == False, PlatformRecord.status.in_(["Received", "Cleared"]))).all()
    people: list[dict[str, Any]] = []
    for user in users:
        candidates = []
        for target in targets:
            data = target.data or {}
            start, end = _date_value(data.get("period_start")), _date_value(data.get("period_end"))
            if target.owner_id == user.id and start and end and start <= today <= end and target.status == "Active":
                candidates.append((start, end, target))
        candidates.sort(key=lambda item: (item[0], item[2].id), reverse=True)
        target_record = candidates[0][2] if candidates else None
        target_data = dict(target_record.data or {}) if target_record else {}
        start = _date_value(target_data.get("period_start")) or date(today.year, today.month, 1)
        end = _date_value(target_data.get("period_end")) or today
        achieved = sum(float(item.amount or 0) for item in payments if item.owner_id == user.id and start <= (_date_value((item.data or {}).get("payment_date")) or item.created_at.date()) <= end)
        target_amount = float(target_data.get("target_amount") or 0)
        achievement = round((achieved / target_amount * 100), 1) if target_amount else 0.0
        rate = float(target_data.get("incentive_rate") or 0)
        threshold = float(target_data.get("threshold_percent") or 80)
        incentive = round(achieved * rate / 100, 2) if achievement >= threshold else 0.0
        conversions = db.scalar(select(func.count()).select_from(Lead).where(Lead.owner_id == user.id, Lead.status == "Converted", Lead.archived == False, Lead.updated_at >= datetime.combine(start, datetime.min.time()), Lead.updated_at <= datetime.combine(end, datetime.max.time()))) or 0
        people.append({"owner_id": user.id, "name": user.name, "role": user.role, "target": target_amount, "achieved": achieved, "achievement_percent": achievement, "conversions": int(conversions), "incentive": incentive, "period_start": start.isoformat(), "period_end": end.isoformat(), "target_configured": target_record is not None})

    stuck_leads = db.scalars(select(Lead).where(Lead.archived == False, Lead.status.not_in(["Converted", "Unqualified"]), or_(Lead.next_follow_up < today, Lead.updated_at < datetime.utcnow() - timedelta(days=7))).order_by(Lead.next_follow_up.asc()).limit(8)).all()
    open_quotes = db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "quotes", PlatformRecord.archived == False, PlatformRecord.status.in_(["Draft", "Pending Approval", "Approved", "Sent"]))).all()
    quote_attention = []
    for quote in open_quotes:
        valid_until = _date_value((quote.data or {}).get("valid_until"))
        if valid_until is None or valid_until <= today + timedelta(days=7):
            quote_attention.append({"id": quote.id, "name": quote.title, "status": quote.status, "valid_until": valid_until.isoformat() if valid_until else None, "owner_id": quote.owner_id})
    attention = {
        "stuck_leads": [{"id": lead.id, "name": lead.name, "status": lead.status, "next_follow_up": lead.next_follow_up.isoformat() if lead.next_follow_up else None, "owner_id": lead.owner_id} for lead in stuck_leads],
        "quotes_needing_follow_up": quote_attention[:8],
    }
    return {"people": people, "attention": attention, "totals": {"target": sum(item["target"] for item in people), "achieved": sum(item["achieved"] for item in people), "incentive": sum(item["incentive"] for item in people)}}


@app.get("/api/analytics/sales-performance")
def sales_performance_api(db: Session = Depends(get_db)) -> dict[str, Any]:
    return sales_performance(db)


@app.get("/api/journey/leads/{lead_id}")
def lead_journey(lead_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if lead is None or lead.archived:
        raise HTTPException(404, "Lead not found")
    deal_ids = {lead.converted_deal_id} if lead.converted_deal_id else set()
    visits = [item for item in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "site_visits", PlatformRecord.archived == False)).all() if int((item.data or {}).get("lead_id") or 0) == lead.id]
    quotes = [item for item in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "quotes", PlatformRecord.archived == False)).all() if item.deal_id in deal_ids]
    quote_ids = {item.id for item in quotes}
    orders = [item for item in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "sales_orders", PlatformRecord.archived == False)).all() if int((item.data or {}).get("quote_id") or 0) in quote_ids]
    order_ids = {item.id for item in orders}
    invoices = [item for item in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "invoices", PlatformRecord.archived == False)).all() if int((item.data or {}).get("sales_order_id") or 0) in order_ids]
    invoice_ids = {item.id for item in invoices}
    payments = [item for item in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == "payments", PlatformRecord.archived == False)).all() if int((item.data or {}).get("invoice_id") or 0) in invoice_ids]
    related_pairs = {("leads", lead.id)} | {("deals", item_id) for item_id in deal_ids}
    activities = [item for item in db.scalars(select(Activity).where(Activity.archived == False).order_by(Activity.created_at.desc())).all() if (item.related_type, item.related_id) in related_pairs]
    emails = [item for item in db.scalars(select(Email).where(Email.archived == False).order_by(Email.created_at.desc())).all() if (item.related_type, item.related_id) in related_pairs]
    return {
        "lead": serialize(lead, db),
        "stages": [
            {"key": "lead", "label": "Lead", "count": 1, "complete": lead.status == "Converted"},
            {"key": "visit", "label": "Visit", "count": len(visits), "complete": any(item.status == "Completed" for item in visits)},
            {"key": "quotation", "label": "Quotation", "count": len(quotes), "complete": bool(quotes)},
            {"key": "invoice", "label": "Invoice", "count": len(invoices), "complete": bool(invoices)},
            {"key": "payment", "label": "Payment", "count": len(payments), "complete": any(item.status in {"Received", "Cleared"} for item in payments)},
        ],
        "visits": [serialize_platform(item, db) for item in visits], "quotes": [serialize_platform(item, db) for item in quotes], "sales_orders": [serialize_platform(item, db) for item in orders], "invoices": [serialize_platform(item, db) for item in invoices], "payments": [serialize_platform(item, db) for item in payments], "activities": [serialize(item, db) for item in activities], "emails": [serialize(item, db) for item in emails],
    }


@app.get("/api/search")
def global_search(q: str = Query(default="", min_length=0), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not q.strip():
        return {"results": []}
    pattern = f"%{q.strip()}%"
    results: list[dict[str, Any]] = []
    for resource, model, columns in [("leads", Lead, ["name", "company", "email"]), ("contacts", Contact, ["first_name", "last_name", "email"]), ("accounts", Account, ["name", "industry"]), ("deals", Deal, ["name", "stage"]), ("products", Product, ["name", "sku", "category"])]:
        clauses = [getattr(model, column).ilike(pattern) for column in columns]
        if resource == "contacts":
            clauses.append((Contact.first_name + " " + Contact.last_name).ilike(pattern))
        for row in db.scalars(select(model).where(or_(*clauses), model.archived == False).limit(5)).all():
            item = serialize(row, db)
            label = item.get("full_name") or item.get("name")
            results.append({"resource": resource, "id": item["id"], "label": label, "meta": item.get("company") or item.get("stage") or item.get("industry")})
    if len(results) < 12:
        platform_rows = db.scalars(select(PlatformRecord).where(PlatformRecord.archived == False, PlatformRecord.title.ilike(pattern)).order_by(PlatformRecord.updated_at.desc()).limit(12 - len(results))).all()
        results.extend({"resource": row.resource, "id": row.id, "label": row.title, "meta": PLATFORM_RESOURCES.get(row.resource, {}).get("label", row.resource), "platform": True} for row in platform_rows)
    return {"results": results[:12]}


@app.get("/api/settings/general")
def get_general_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    return serialize(get_or_create_settings(db))


@app.put("/api/settings/general")
def update_general_settings(payload: SettingsPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    setting = get_or_create_settings(db)
    before = serialize(setting)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        if key in {"id"} or not hasattr(setting, key) or value is None:
            continue
        if isinstance(value, str) and not value.strip():
            raise HTTPException(422, f"{key.replace('_', ' ').capitalize()} cannot be empty")
        setattr(setting, key, value)
    add_audit(db, "update", "general_settings", setting.id, "Updated general settings", before=before, after=serialize(setting))
    db.commit()
    db.refresh(setting)
    return serialize(setting)


@app.get("/api/settings/profile")
def get_profile(db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).order_by(User.id).limit(1))
    if user is None:
        raise HTTPException(404, "Profile not found")
    return serialize(user, db)


@app.put("/api/settings/profile")
def update_profile(payload: SettingsPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).order_by(User.id).limit(1))
    if user is None:
        raise HTTPException(404, "Profile not found")
    before = serialize(user, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"id", "role", "status"} or not hasattr(user, key):
            continue
        if key == "name" and not (value or "").strip():
            raise HTTPException(422, "Name cannot be empty")
        if key == "email":
            email = (value or "").strip().lower()
            if not email or parseaddr(email)[1] != email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                raise HTTPException(422, "Enter a valid email address")
            duplicate = db.scalar(select(User).where(func.lower(User.email) == email, User.id != user.id))
            if duplicate:
                raise HTTPException(409, "That email address is already used by another user")
            value = email
        setattr(user, key, value)
    add_audit(db, "update", "personal_settings", user.id, "Updated personal settings", before=before, after=serialize(user, db), actor_id=user.id)
    db.commit()
    db.refresh(user)
    return serialize(user, db)


@app.get("/api/platform/catalog")
def get_platform_catalog() -> dict[str, Any]:
    return {"resources": public_catalog(), "setup_navigation": SETUP_NAVIGATION}


@app.get("/api/platform/{resource}")
def list_platform_records(
    resource: str,
    search: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    sort: str = "updated_desc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    platform_config(resource)
    query = select(PlatformRecord).where(PlatformRecord.resource == resource)
    if not include_archived:
        query = query.where(PlatformRecord.archived == False)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(PlatformRecord.title.ilike(pattern), PlatformRecord.status.ilike(pattern)))
    if status:
        query = query.where(PlatformRecord.status == status)
    if owner_id:
        query = query.where(PlatformRecord.owner_id == owner_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    ordering = {
        "created_asc": PlatformRecord.created_at.asc(),
        "created_desc": PlatformRecord.created_at.desc(),
        "updated_asc": PlatformRecord.updated_at.asc(),
        "updated_desc": PlatformRecord.updated_at.desc(),
        "name_asc": PlatformRecord.title.asc(),
        "name_desc": PlatformRecord.title.desc(),
        "amount_desc": PlatformRecord.amount.desc(),
    }.get(sort, PlatformRecord.updated_at.desc())
    rows = db.scalars(query.order_by(ordering).limit(limit).offset(offset)).all()
    return {"items": [serialize_platform(row, db) for row in rows], "total": int(total), "limit": limit, "offset": offset}


@app.post("/api/platform/{resource}", status_code=201)
def create_platform_record(resource: str, payload: PlatformPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    config = platform_config(resource)
    values = platform_values(payload)
    normalize_platform_links(db, resource, values)
    validate_platform_values(resource, values)
    if config.get("singleton") and db.scalar(select(PlatformRecord.id).where(PlatformRecord.resource == resource, PlatformRecord.archived == False)):
        raise HTTPException(409, f"{config['label']} already has an active record")
    apply_assignment_rule(db, resource, values)
    title = str(values.get("name") or values.get("title") or "").strip()
    record = PlatformRecord(resource=resource, title=title or config["singular"], data={})
    sync_platform_columns(record, values)
    db.add(record)
    db.flush()
    ensure_transaction_number(record)
    if resource == "payments":
        refresh_invoice_balance(db, int(values["invoice_id"]))
    run_platform_automation(db, resource, "create", record, values)
    add_audit(db, "create", resource, record.id, f"Created {config['singular']} '{record.title}'", after=serialize_platform(record))
    db.commit()
    db.refresh(record)
    return serialize_platform(record, db)


@app.get("/api/platform/{resource}/{item_id}")
def get_platform_record(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    platform_config(resource)
    record = db.scalar(select(PlatformRecord).where(PlatformRecord.resource == resource, PlatformRecord.id == item_id))
    if record is None or record.archived:
        raise HTTPException(404, "Record not found")
    return serialize_platform(record, db)


@app.get("/api/platform/{resource}/{item_id}/related")
def get_platform_related(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    platform_config(resource)
    record = db.scalar(select(PlatformRecord).where(PlatformRecord.resource == resource, PlatformRecord.id == item_id, PlatformRecord.archived == False))
    if record is None:
        raise HTTPException(404, "Record not found")
    linked: dict[str, list[dict[str, Any]]] = {"accounts": [], "contacts": [], "deals": [], "activities": [], "platform_records": []}
    for key, model, identifier in (("accounts", Account, record.account_id), ("contacts", Contact, record.contact_id), ("deals", Deal, record.deal_id)):
        if identifier:
            row = db.get(model, identifier)
            if row is not None and not getattr(row, "archived", False):
                linked[key].append(serialize(row, db))
    linked["activities"] = [serialize(row, db) for row in db.scalars(select(Activity).where(Activity.related_type == resource, Activity.related_id == item_id, Activity.archived == False).order_by(Activity.created_at.desc())).all()]
    linked["platform_records"] = [serialize_platform(row, db) for row in db.scalars(select(PlatformRecord).where(PlatformRecord.related_type == resource, PlatformRecord.related_id == item_id, PlatformRecord.archived == False).order_by(PlatformRecord.updated_at.desc())).all()]
    return linked


@app.patch("/api/platform/{resource}/{item_id}")
def update_platform_record(resource: str, item_id: int, payload: PlatformPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    config = platform_config(resource)
    record = db.scalar(select(PlatformRecord).where(PlatformRecord.resource == resource, PlatformRecord.id == item_id))
    if record is None or record.archived:
        raise HTTPException(404, "Record not found")
    before = serialize_platform(record)
    changes = platform_values(payload)
    validate_platform_values(resource, changes, partial=True)
    values = dict(record.data or {})
    values.update(changes)
    normalize_platform_links(db, resource, values)
    validate_platform_values(resource, values)
    sync_platform_columns(record, values)
    ensure_transaction_number(record)
    if resource == "payments":
        refresh_invoice_balance(db, int(values["invoice_id"]))
    run_platform_automation(db, resource, "update", record, values)
    add_audit(db, "update", resource, item_id, f"Updated {config['singular']} '{record.title}'", before=before, after=serialize_platform(record))
    db.commit()
    db.refresh(record)
    return serialize_platform(record, db)


@app.delete("/api/platform/{resource}/{item_id}")
def archive_platform_record(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    config = platform_config(resource)
    record = db.scalar(select(PlatformRecord).where(PlatformRecord.resource == resource, PlatformRecord.id == item_id))
    if record is None or record.archived:
        raise HTTPException(404, "Record not found")
    before = serialize_platform(record)
    record.archived = True
    if resource == "payments" and (record.data or {}).get("invoice_id"):
        db.flush()
        refresh_invoice_balance(db, int(record.data["invoice_id"]))
    add_audit(db, "archive", resource, item_id, f"Archived {config['singular']} '{record.title}'", before=before)
    db.commit()
    return {"ok": True, "id": item_id, "archived": True}


@app.post("/api/platform/{resource}/{item_id}/restore")
def restore_platform_record(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    config = platform_config(resource)
    record = db.scalar(select(PlatformRecord).where(PlatformRecord.resource == resource, PlatformRecord.id == item_id))
    if record is None:
        raise HTTPException(404, "Record not found")
    record.archived = False
    add_audit(db, "restore", resource, item_id, f"Restored {config['singular']} '{record.title}'", after=serialize_platform(record))
    db.commit()
    db.refresh(record)
    return serialize_platform(record, db)


@app.get("/api/audit")
def audit_history(
    resource: str | None = None,
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(AuditEvent)
    if resource:
        query = query.where(AuditEvent.resource == resource)
    if action:
        query = query.where(AuditEvent.action == action)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(AuditEvent.occurred_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [{"id": row.id, "occurred_at": row.occurred_at.isoformat(), "actor_id": row.actor_id, "action": row.action, "resource": row.resource, "record_id": row.record_id, "summary": row.summary, "before": row.before, "after": row.after} for row in rows], "total": int(total), "limit": limit, "offset": offset}


@app.get("/api/administration/recycle-bin")
def recycle_bin(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for resource, model in RESOURCE_MAP.items():
        if not hasattr(model, "archived"):
            continue
        rows = db.scalars(select(model).where(getattr(model, "archived") == True).limit(limit)).all()
        for row in rows:
            serialized = serialize(row, db)
            items.append({"resource": resource, "id": row.id, "name": serialized.get("name") or serialized.get("full_name") or serialized.get("subject") or serialized.get("title") or f"#{row.id}", "archived_at": serialized.get("updated_at")})
    rows = db.scalars(select(PlatformRecord).where(PlatformRecord.archived == True).order_by(PlatformRecord.updated_at.desc()).limit(limit)).all()
    items.extend({"resource": row.resource, "id": row.id, "name": row.title, "archived_at": row.updated_at.isoformat() if row.updated_at else None, "platform": True} for row in rows)
    items.sort(key=lambda item: item.get("archived_at") or "", reverse=True)
    return {"items": items[:limit], "total": len(items)}


@app.post("/api/administration/restore")
def restore_archived(payload: RestorePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.resource in PLATFORM_RESOURCES:
        record = db.scalar(select(PlatformRecord).where(PlatformRecord.resource == payload.resource, PlatformRecord.id == payload.record_id))
    else:
        model = RESOURCE_MAP.get(payload.resource)
        record = db.get(model, payload.record_id) if model and hasattr(model, "archived") else None
    if record is None:
        raise HTTPException(404, "Archived record not found")
    record.archived = False
    add_audit(db, "restore", payload.resource, payload.record_id, "Restored record from recycle bin")
    db.commit()
    return {"ok": True, "resource": payload.resource, "id": payload.record_id}


@app.get("/api/administration/duplicates")
def duplicate_candidates(resource: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    if resource in PLATFORM_RESOURCES:
        rows = db.execute(select(func.lower(PlatformRecord.title), func.count(PlatformRecord.id)).where(PlatformRecord.resource == resource, PlatformRecord.archived == False).group_by(func.lower(PlatformRecord.title)).having(func.count(PlatformRecord.id) > 1)).all()
        for normalized, count in rows:
            matches = db.scalars(select(PlatformRecord).where(PlatformRecord.resource == resource, func.lower(PlatformRecord.title) == normalized, PlatformRecord.archived == False)).all()
            groups.append({"match_on": "name", "value": normalized, "count": int(count), "records": [serialize_platform(row, db) for row in matches]})
    elif resource in {"leads", "contacts", "users"}:
        model = RESOURCE_MAP[resource]
        email_column = getattr(model, "email")
        query = select(func.lower(email_column), func.count(model.id)).where(email_column.is_not(None)).group_by(func.lower(email_column)).having(func.count(model.id) > 1)
        if hasattr(model, "archived"):
            query = query.where(getattr(model, "archived") == False)
        for normalized, count in db.execute(query).all():
            matches = db.scalars(select(model).where(func.lower(email_column) == normalized)).all()
            groups.append({"match_on": "email", "value": normalized, "count": int(count), "records": [serialize(row, db) for row in matches]})
    else:
        raise HTTPException(422, "Duplicate detection currently supports platform modules, leads, contacts and users")
    return {"resource": resource, "groups": groups, "duplicate_groups": len(groups)}


@app.get("/api/export/{resource}.csv")
def export_csv(resource: str, db: Session = Depends(get_db)) -> StreamingResponse:
    if resource in PLATFORM_RESOURCES:
        rows = [serialize_platform(row, db) for row in db.scalars(select(PlatformRecord).where(PlatformRecord.resource == resource, PlatformRecord.archived == False)).all()]
    elif resource in RESOURCE_MAP:
        model = RESOURCE_MAP[resource]
        query = select(model)
        if hasattr(model, "archived"):
            query = query.where(getattr(model, "archived") == False)
        rows = [serialize(row, db) for row in db.scalars(query).all()]
    else:
        raise HTTPException(404, "Unknown export resource")
    keys = sorted({key for row in rows for key in row.keys() if key not in {"data"}}) or ["id", "name"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    content = stream.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="yash-crm-{resource}.csv"'})


@app.post("/api/import/{resource}")
async def import_csv(resource: str, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    config = platform_config(resource)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Upload a CSV file")
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "CSV files are limited to 5 MB")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(422, "CSV must use UTF-8 encoding") from error
    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    errors: list[dict[str, Any]] = []
    for number, row in enumerate(reader, start=2):
        values = {key.strip(): value.strip() for key, value in row.items() if key and value is not None and value.strip() != ""}
        try:
            with db.begin_nested():
                validate_platform_values(resource, values)
                record = PlatformRecord(resource=resource, title=str(values.get("name") or config["singular"]), data={})
                sync_platform_columns(record, values)
                db.add(record)
                db.flush()
                add_audit(db, "import", resource, record.id, f"Imported {config['singular']} '{record.title}'")
            imported += 1
        except Exception as error:
            errors.append({"row": number, "error": str(getattr(error, "detail", error))[:240]})
    job = ImportJob(resource=resource, filename=file.filename or "upload.csv", status="Completed with errors" if errors else "Completed", total_rows=imported + len(errors), imported_rows=imported, error_rows=len(errors), errors=errors[:100])
    db.add(job)
    db.commit()
    return {"job_id": job.id, "resource": resource, "imported": imported, "errors": errors, "status": job.status}


@app.get("/api/import-jobs")
def import_jobs(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(100)).all()
    return {"items": [{"id": row.id, "resource": row.resource, "filename": row.filename, "status": row.status, "total_rows": row.total_rows, "imported_rows": row.imported_rows, "error_rows": row.error_rows, "errors": row.errors, "created_at": row.created_at.isoformat()} for row in rows]}


@app.post("/api/documents/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    name: str = Form(...),
    document_type: str | None = Form(None),
    version: str | None = Form(None),
    related_type: str | None = Form(None),
    related_id: int | None = Form(None),
    owner_id: int | None = Form(None),
    status: str = Form("Active"),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    original = Path(file.filename or "").name
    extension = Path(original).suffix.lower()
    allowed = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg"}
    if extension not in allowed:
        raise HTTPException(422, "Upload a PDF, Office document, CSV, text file, PNG or JPEG")
    content = await file.read(10_000_001)
    if not content:
        raise HTTPException(422, "The selected document is empty")
    if len(content) > 10_000_000:
        raise HTTPException(413, "Documents are limited to 10 MB")
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(original).stem).strip("-._")[:80] or "document"
    stored_name = f"{datetime.utcnow():%Y%m%d%H%M%S}-{secrets.token_hex(5)}-{safe_stem}{extension}"
    DOCUMENT_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    target = DOCUMENT_UPLOAD_ROOT / stored_name
    target.write_bytes(content)
    values: dict[str, Any] = {
        "name": name.strip(), "document_type": document_type or extension.lstrip(".").upper(),
        "url": f"/uploads/documents/{stored_name}", "version": version, "related_type": related_type,
        "related_id": related_id, "owner_id": owner_id, "status": status, "description": description,
        "file_name": original, "file_size": len(content), "content_type": file.content_type,
    }
    try:
        return create_platform_record("documents", PlatformPayload(**values), db)
    except Exception:
        target.unlink(missing_ok=True)
        raise


@app.get("/api/{resource}")
def get_collection(resource: str, search: str | None = None, status: str | None = None, owner_id: int | None = None, sort: str = "created_desc", min_amount: float | None = None, max_amount: float | None = None, close_from: date | None = None, close_to: date | None = None, activity_type: str | None = None, limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> dict[str, Any]:
    if resource not in RESOURCE_MAP:
        raise HTTPException(404, "Resource not found")
    return list_resource(db, resource, search, status, owner_id, sort, min_amount, max_amount, close_from, close_to, limit, offset, activity_type)


@app.post("/api/leads/bulk-archive")
def bulk_archive_leads(payload: BulkArchivePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    ids = list(dict.fromkeys(payload.related_id))
    if not ids:
        raise HTTPException(422, "related_id must contain at least one lead ID")
    if len(ids) > 100:
        raise HTTPException(422, "A maximum of 100 leads can be archived at once")
    leads = db.scalars(select(Lead).where(Lead.id.in_(ids))).all()
    for lead in leads:
        lead.archived = True
        add_audit(db, "archive", "leads", lead.id, f"Archived lead '{lead.name}'")
    db.commit()
    return {"ok": True, "archived": len(leads)}


@app.post("/api/{resource}")
def create_record(resource: str, payload: RecordPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    if resource not in RESOURCE_MAP:
        raise HTTPException(404, "Resource not found")
    model = RESOURCE_MAP[resource]
    values = {}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"id", "created_at", "updated_at"} or model.__table__.columns.get(key) is None or value is None:
            continue
        values[key] = coerce_value(model, key, value)
    if resource == "users" and not (values.get("name") and values.get("email")):
        raise HTTPException(422, "Name and email are required")
    if resource == "approval_processes" and not values.get("name"):
        raise HTTPException(422, "Rule name is required")
    if resource == "blueprints" and not values.get("name"):
        raise HTTPException(422, "Blueprint name is required")
    if resource == "contacts" and not values.get("first_name"):
        raise HTTPException(422, "First name is required")
    if resource in {"leads", "accounts", "deals", "products"} and not values.get("name"):
        raise HTTPException(422, "Name is required")
    if resource == "activities" and not values.get("subject"):
        raise HTTPException(422, "Subject is required")
    if resource in {"notes", "attachments"} and not values.get("name", values.get("title")):
        raise HTTPException(422, "A name or title is required")
    if resource == "emails" and not values.get("subject"):
        raise HTTPException(422, "Subject is required")
    if resource == "deals":
        stage = values.get("stage", "Qualification")
        values.setdefault("probability", STAGE_PROBABILITY.get(stage, 20))
        values.setdefault("status", STAGE_STATUS.get(stage, "Open"))
    item = model(**values)
    if resource == "activities" and item.status == "Completed" and item.completed_at is None:
        item.completed_at = datetime.utcnow()
    db.add(item)
    db.flush()
    created = serialize(item, db)
    add_audit(db, "create", resource, item.id, f"Created {resource.rstrip('s')} record", after=created)
    db.commit()
    db.refresh(item)
    return serialize(item, db)


@app.get("/api/{resource}/{item_id}")
def get_record(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    if resource not in RESOURCE_MAP:
        raise HTTPException(404, "Resource not found")
    item = db.get(RESOURCE_MAP[resource], item_id)
    if item is None or getattr(item, "archived", False):
        raise HTTPException(404, "Record not found")
    return serialize(item, db)


@app.patch("/api/{resource}/{item_id}")
def update_record(resource: str, item_id: int, payload: RecordPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    if resource not in RESOURCE_MAP:
        raise HTTPException(404, "Resource not found")
    item = db.get(RESOURCE_MAP[resource], item_id)
    if item is None:
        raise HTTPException(404, "Record not found")
    model = RESOURCE_MAP[resource]
    before_full = serialize(item, db)
    before = (getattr(item, "stage", None), getattr(item, "probability", None), getattr(item, "status", None))
    for key, value in payload.model_dump(exclude_unset=True).items():
        column = model.__table__.columns.get(key)
        if key in {"id", "created_at", "updated_at"} or column is None:
            continue
        if value is None and not column.nullable:
            continue
        setattr(item, key, coerce_value(model, key, value))
    if resource == "deals" and item.stage != before[0] and item.stage in STAGE_PROBABILITY:
        if item.probability == before[1]:
            item.probability = STAGE_PROBABILITY[item.stage]
        if item.status == before[2]:
            item.status = STAGE_STATUS.get(item.stage, "Open")
    if resource == "activities" and getattr(item, "status", None) == "Completed" and item.completed_at is None:
        item.completed_at = datetime.utcnow()
    if resource == "activities" and getattr(item, "status", None) != "Completed":
        item.completed_at = None
    add_audit(db, "update", resource, item_id, f"Updated {resource.rstrip('s')} record", before=before_full, after=serialize(item, db))
    db.commit()
    db.refresh(item)
    return serialize(item, db)


@app.delete("/api/{resource}/{item_id}")
def delete_record(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    if resource not in RESOURCE_MAP:
        raise HTTPException(404, "Resource not found")
    item = db.get(RESOURCE_MAP[resource], item_id)
    if item is None:
        raise HTTPException(404, "Record not found")
    if resource == "users":
        item.status = "Inactive"
        add_audit(db, "deactivate", resource, item_id, "Deactivated user", before=serialize(item, db))
        db.commit()
        return {"ok": True, "id": item_id, "archived": True}
    if hasattr(item, "archived"):
        before = serialize(item, db)
        item.archived = True
        add_audit(db, "archive", resource, item_id, f"Archived {resource.rstrip('s')} record", before=before)
    else:
        add_audit(db, "delete", resource, item_id, f"Deleted {resource.rstrip('s')} configuration", before=serialize(item, db))
        db.delete(item)
    db.commit()
    return {"ok": True, "id": item_id, "archived": hasattr(item, "archived")}


@app.get("/api/{resource}/{item_id}/related")
def related_records(resource: str, item_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    if resource not in RESOURCE_MAP:
        raise HTTPException(404, "Resource not found")
    if db.get(RESOURCE_MAP[resource], item_id) is None:
        raise HTTPException(404, "Record not found")
    related: dict[str, list[dict[str, Any]]] = {"activities": [], "contacts": [], "accounts": [], "deals": [], "leads": [], "products": [], "notes": [], "attachments": [], "emails": []}
    if resource == "accounts":
        related["contacts"] = [serialize(item, db) for item in db.scalars(select(Contact).where(Contact.account_id == item_id, Contact.archived == False)).all()]
        related["deals"] = [serialize(item, db) for item in db.scalars(select(Deal).where(Deal.account_id == item_id, Deal.archived == False)).all()]
        related["activities"] = [serialize(item, db) for item in db.scalars(select(Activity).where(Activity.related_type == "accounts", Activity.related_id == item_id, Activity.archived == False).order_by(Activity.created_at.desc())).all()]
    elif resource == "contacts":
        contact = db.get(Contact, item_id)
        if contact and contact.account_id:
            account = db.get(Account, contact.account_id)
            if account:
                related["accounts"] = [serialize(account, db)]
        related["deals"] = [serialize(item, db) for item in db.scalars(select(Deal).where(Deal.contact_id == item_id, Deal.archived == False)).all()]
        related["activities"] = [serialize(item, db) for item in db.scalars(select(Activity).where(Activity.related_type == "contacts", Activity.related_id == item_id, Activity.archived == False).order_by(Activity.created_at.desc())).all()]
    elif resource == "leads":
        lead = db.get(Lead, item_id)
        related["activities"] = [serialize(item, db) for item in db.scalars(select(Activity).where(Activity.related_type == "leads", Activity.related_id == item_id, Activity.archived == False).order_by(Activity.created_at.desc())).all()]
        if lead and lead.converted_account_id:
            account = db.get(Account, lead.converted_account_id)
            if account:
                related["accounts"] = [serialize(account, db)]
        if lead and lead.converted_contact_id:
            contact = db.get(Contact, lead.converted_contact_id)
            if contact:
                related["contacts"] = [serialize(contact, db)]
        if lead and lead.converted_deal_id:
            deal = db.get(Deal, lead.converted_deal_id)
            if deal:
                related["deals"] = [serialize(deal, db)]
    elif resource == "deals":
        deal = db.get(Deal, item_id)
        if deal and deal.account_id:
            account = db.get(Account, deal.account_id)
            if account:
                related["accounts"] = [serialize(account, db)]
        if deal and deal.contact_id:
            contact = db.get(Contact, deal.contact_id)
            if contact:
                related["contacts"] = [serialize(contact, db)]
        related["activities"] = [serialize(item, db) for item in db.scalars(select(Activity).where(Activity.related_type == "deals", Activity.related_id == item_id, Activity.archived == False).order_by(Activity.created_at.desc())).all()]
    for key, model in {"products": Product, "notes": Note, "attachments": Attachment, "emails": Email}.items():
        related[key] = [serialize(item, db) for item in db.scalars(select(model).where(model.related_type == resource, model.related_id == item_id, model.archived == False).order_by(model.created_at.desc())).all()]
    return related


@app.post("/api/leads/{item_id}/convert")
def convert_lead(item_id: int, payload: RecordPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    lead = db.get(Lead, item_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    if lead.archived:
        raise HTTPException(409, "Archived leads cannot be converted")
    values = payload.model_dump(exclude_unset=True)
    LEAD_CONVERSION_LOCK.acquire()
    try:
        db.refresh(lead)
        account = db.get(Account, lead.converted_account_id) if lead.converted_account_id else None
        if account is None:
            account_name = (values.get("account_name") or lead.company or f"{lead.name} account").strip()
            account = db.scalar(select(Account).where(func.lower(Account.name) == account_name.lower(), Account.archived == False))
            if account is None:
                account = Account(name=account_name, phone=lead.phone, type="Prospect", owner_id=lead.owner_id, status="Active", notes=f"Created from lead {lead.name}.", tags=["converted-lead"])
                db.add(account); db.flush()

        contact = db.get(Contact, lead.converted_contact_id) if lead.converted_contact_id else None
        if contact is None:
            if lead.email:
                contact = db.scalar(select(Contact).where(func.lower(Contact.email) == lead.email.lower(), Contact.archived == False))
            if contact is None:
                parts = lead.name.split(" ", 1)
                contact = Contact(first_name=parts[0], last_name=parts[1] if len(parts) > 1 else "", email=lead.email, phone=lead.phone, account_id=account.id, owner_id=lead.owner_id, notes=f"Converted from lead {lead.name}.", tags=["converted"])
                db.add(contact); db.flush()
            elif contact.account_id is None:
                contact.account_id = account.id

        deal = db.get(Deal, lead.converted_deal_id) if lead.converted_deal_id else None
        if deal is None:
            # A converted lead always owns exactly one conversion deal. This also repairs legacy partial conversions.
            deal = Deal(name=(values.get("deal_name") or f"{account.name} opportunity").strip(), account_id=account.id, contact_id=contact.id, amount=float(values.get("deal_amount") or 0), stage="Qualification", probability=20, expected_close_date=parse_date_value(values.get("expected_close_date")), owner_id=lead.owner_id, type="New business", source="Lead conversion", status="Open", notes=f"Created from lead #{lead.id} conversion.")
            db.add(deal); db.flush()

        lead.status = "Converted"
        lead.converted_account_id, lead.converted_contact_id, lead.converted_deal_id = account.id, contact.id, deal.id
        add_audit(db, "convert", "leads", lead.id, f"Converted lead '{lead.name}' to account, contact and deal", before={"status": "Converted" if lead.converted_deal_id else lead.status}, after={"account_id": account.id, "contact_id": contact.id, "deal_id": deal.id}, actor_id=lead.owner_id)
        db.commit()
        for record in (lead, account, contact, deal): db.refresh(record)
        return {"lead": serialize(lead, db), "account": serialize(account, db), "contact": serialize(contact, db), "deal": serialize(deal, db)}
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise
    finally:
        LEAD_CONVERSION_LOCK.release()


@app.get("/{path:path}", response_class=HTMLResponse)
def spa_fallback(path: str) -> FileResponse:
    if path.startswith("api/") or path.startswith("static/"):
        raise HTTPException(404, "Not found")
    return FileResponse(ROOT / "templates" / "index.html", media_type="text/html")
