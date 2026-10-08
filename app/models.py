from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON as SAJSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
    username: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(80), default="Sales rep")
    status: Mapped[str] = mapped_column(String(30), default="Active")
    last_active: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manager_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    territory_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_status: Mapped[str] = mapped_column(String(30), default="Unknown")
    personal_data_classification: Mapped[str] = mapped_column(String(30), default="Normal")
    sensitive_data: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Territory(TimestampMixin, Base):
    __tablename__ = "territories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    criteria: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    visibility: Mapped[str] = mapped_column(String(40), default="Private")
    forecasting: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_territory_org_name"),)


class SecurityGroup(TimestampMixin, Base):
    __tablename__ = "security_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    group_type: Mapped[str] = mapped_column(String(40), default="Users")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_security_group_org_name"),)


class SecurityGroupMember(Base):
    __tablename__ = "security_group_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("security_groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_role: Mapped[str] = mapped_column(String(30), default="Member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_security_group_member"),)


class LoginHistory(Base):
    __tablename__ = "login_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(30))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", SAJSON, default=dict)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Active", index=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)


class OrganizationMember(TimestampMixin, Base):
    __tablename__ = "organization_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_role: Mapped[str] = mapped_column(String(30), default="Member")
    status: Mapped[str] = mapped_column(String(30), default="Active", index=True)
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),)


class Plan(TimestampMixin, Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    price_monthly: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    max_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_storage_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_custom_modules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_limit_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    features: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class OrganizationSubscription(TimestampMixin, Base):
    __tablename__ = "organization_subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(180), index=True)
    membership_role: Mapped[str] = mapped_column(String(30), default="Member")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SubscriptionChangeRequest(Base):
    __tablename__ = "subscription_change_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    to_plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending Payment", index=True)
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BillingWebhookEvent(Base):
    __tablename__ = "billing_webhook_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    event_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("subscription_change_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Received", index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PrivacyRecord(TimestampMixin, Base):
    __tablename__ = "privacy_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(40))
    subject_id: Mapped[int] = mapped_column(Integer)
    consent_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    classification: Mapped[str] = mapped_column(String(30))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", SAJSON, default=dict)
    __table_args__ = (Index("ix_privacy_records_subject", "subject_type", "subject_id"),)


class OwnershipTransfer(TimestampMixin, Base):
    __tablename__ = "ownership_transfers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    from_user_id: Mapped[int] = mapped_column(Integer)
    to_user_id: Mapped[int] = mapped_column(Integer)
    resources: Mapped[list[str]] = mapped_column(SAJSON, default=list)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="Completed")
    requested_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Teamspace(TimestampMixin, Base):
    __tablename__ = "teamspaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    icon: Mapped[str] = mapped_column(String(40), default="◈")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    modules: Mapped[list[str]] = mapped_column(SAJSON, default=list)
    folders: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class TeamspaceMember(Base):
    __tablename__ = "teamspace_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teamspace_id: Mapped[int] = mapped_column(ForeignKey("teamspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_role: Mapped[str] = mapped_column(String(30), default="Member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("teamspace_id", "user_id", name="uq_teamspace_member"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="info")
    title: Mapped[str] = mapped_column(String(220))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource: Mapped[str | None] = mapped_column(String(80), nullable=True)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(300))
    resource: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class MetadataModule(TimestampMixin, Base):
    __tablename__ = "metadata_modules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_name: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(160))
    plural_label: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    config: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    __table_args__ = (UniqueConstraint("organization_id", "api_name", name="uq_metadata_module_org_api_name"),)


class MetadataField(TimestampMixin, Base):
    __tablename__ = "metadata_fields"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("metadata_modules.id", ondelete="CASCADE"), index=True)
    api_name: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(160))
    field_type: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    unique_value: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[Any | None] = mapped_column(SAJSON, nullable=True)
    validation: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, nullable=True)
    permissions: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, nullable=True)
    visibility: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, nullable=True)
    __table_args__ = (UniqueConstraint("module_id", "api_name", name="uq_metadata_field_api_name"),)


class MetadataLayout(TimestampMixin, Base):
    __tablename__ = "metadata_layouts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("metadata_modules.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    assignment: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)


class MetadataView(TimestampMixin, Base):
    __tablename__ = "metadata_views"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("metadata_modules.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)
    columns: Mapped[list[str]] = mapped_column(SAJSON, default=list)
    sorting: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)
    visibility: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)


class PermissionProfile(TimestampMixin, Base):
    __tablename__ = "permission_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    grants: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_permission_profile_org_name"),)


class SharingPolicy(TimestampMixin, Base):
    __tablename__ = "sharing_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    module: Mapped[str] = mapped_column(String(100), index=True)
    scope: Mapped[str] = mapped_column(String(40), default="Private")
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)
    access: Mapped[str] = mapped_column(String(30), default="Read Only")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("platform_records.id"), index=True)
    resource: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[int] = mapped_column(Integer, index=True)
    event: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), index=True)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(SAJSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BlueprintTransitionLog(Base):
    __tablename__ = "blueprint_transition_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    blueprint_id: Mapped[int] = mapped_column(ForeignKey("blueprints.id"), index=True)
    module: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[int] = mapped_column(Integer, index=True)
    from_stage: Mapped[str] = mapped_column(String(100))
    to_stage: Mapped[str] = mapped_column(String(100))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requirements: Mapped[list[str]] = mapped_column(SAJSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[str] = mapped_column(String(30), default="Task")
    subject: Mapped[str] = mapped_column(String(180))
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Open")
    priority: Mapped[str] = mapped_column(String(30), default="Normal")
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class OrganizationSetting(Base):
    __tablename__ = "organization_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    org_name: Mapped[str] = mapped_column(String(160), default="CONVOSIS CRM")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    date_format: Mapped[str] = mapped_column(String(30), default="DD MMM YYYY")
    fiscal_year_start: Mapped[str] = mapped_column(String(20), default="April")
    default_pipeline: Mapped[str] = mapped_column(String(80), default="Default sales pipeline")
    notifications: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, default=dict)


class ApprovalProcess(TimestampMixin, Base):
    __tablename__ = "approval_processes"
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    module: Mapped[str] = mapped_column(String(50), default="Deals")
    trigger: Mapped[str] = mapped_column(String(180), default="Amount is greater than 0")
    approver: Mapped[str] = mapped_column(String(120), default="Sales manager")
    status: Mapped[str] = mapped_column(String(30), default="Active")
    conditions: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)
    steps: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("approval_processes.id"), index=True)
    resource: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[int] = mapped_column(Integer, index=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    operation_key: Mapped[str] = mapped_column(String(180), unique=True)


class ApprovalStepDecision(Base):
    __tablename__ = "approval_step_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approver_label: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="Waiting", index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    delegated_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("request_id", "step_order", name="uq_approval_request_step"),)


class ReportRun(Base):
    __tablename__ = "report_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("platform_records.id"), index=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    definition: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApexAssistantRun(Base):
    __tablename__ = "apex_assistant_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(1500))
    intent: Mapped[str] = mapped_column(String(40), index=True)
    scope: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict[str, Any]] = mapped_column(SAJSON, default=dict)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Blueprint(Base):
    __tablename__ = "blueprints"
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id"), nullable=True, index=True)
    related_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DocumentBlob(Base):
    __tablename__ = "document_blobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("platform_records.id", ondelete="CASCADE"), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(220))
    content_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIExceptionOccurrence(TimestampMixin, Base):
    __tablename__ = "ai_exception_occurrences"
    __table_args__ = (UniqueConstraint("active_key", name="uq_ai_exception_active_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rule_version: Mapped[str] = mapped_column(String(80), index=True)
    source_resource: Mapped[str] = mapped_column(String(80), default="quotes")
    source_id: Mapped[int] = mapped_column(Integer, index=True)
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    trigger_kind: Mapped[str] = mapped_column(String(50), index=True)
    review_state: Mapped[str] = mapped_column(String(30), default="open", index=True)
    active_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    predecessor_id: Mapped[int | None] = mapped_column(ForeignKey("ai_exception_occurrences.id"), nullable=True)
    dismissed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    facts: Mapped[dict[str, Any] | None] = mapped_column(SAJSON, default=dict)


class AIExceptionEvent(Base):
    __tablename__ = "ai_exception_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("ai_exception_occurrences.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    from_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_state: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rule_version: Mapped[str] = mapped_column(String(80))
    source_version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AITaskProposal(TimestampMixin, Base):
    __tablename__ = "ai_task_proposals"
    __table_args__ = (UniqueConstraint("public_id", "version", name="uq_ai_task_proposal_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("ai_exception_occurrences.id"), index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    intent_code: Mapped[str] = mapped_column(String(50), default="quote_follow_up")
    subject: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(1000), default="")
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    due_at: Mapped[datetime] = mapped_column(DateTime)
    operation_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(180), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AITaskOperation(Base):
    __tablename__ = "ai_task_operations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("ai_task_proposals.id"))
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
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
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    resource: Mapped[str] = mapped_column(String(80), index=True)
    filename: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(40), default="Completed")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(SAJSON, default=list)

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "AuthSession",
    "PasswordResetToken",
    "Territory",
    "SecurityGroup",
    "SecurityGroupMember",
    "LoginHistory",
    "Organization",
    "OrganizationMember",
    "Plan",
    "Subscription",
    "OrganizationSubscription",
    "OrganizationInvitation",
    "SubscriptionChangeRequest",
    "BillingWebhookEvent",
    "PrivacyRecord",
    "OwnershipTransfer",
    "Teamspace",
    "TeamspaceMember",
    "Notification",
    "ApiRequestLog",
    "MetadataModule",
    "MetadataField",
    "MetadataLayout",
    "MetadataView",
    "PermissionProfile",
    "SharingPolicy",
    "WorkflowExecution",
    "BlueprintTransitionLog",
    "Lead",
    "Account",
    "Contact",
    "Deal",
    "Product",
    "Note",
    "Attachment",
    "Email",
    "Activity",
    "OrganizationSetting",
    "ApprovalProcess",
    "ApprovalRequest",
    "ApprovalStepDecision",
    "ReportRun",
    "ApexAssistantRun",
    "Blueprint",
    "PlatformRecord",
    "DocumentBlob",
    "AIExceptionOccurrence",
    "AIExceptionEvent",
    "AITaskProposal",
    "AITaskOperation",
    "AuditEvent",
    "ImportJob"
]
