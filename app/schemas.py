from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
    body: str | None = None
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


class AIProposedActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_type: str = Field(pattern="^(Task|Call|Meeting)$")
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=1, max_length=1200)
    due_at: datetime
    priority: str = Field(default="Normal", pattern="^(Low|Normal|High)$")
    related_type: str = Field(pattern="^(leads|contacts|accounts|deals)$")
    related_id: int = Field(ge=1)
    owner_id: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1, max_length=500)


class AIChatPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1500)
    lead_id: int | None = Field(default=None, ge=1)


class AIInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=5000)
    actions: list[str] = Field(default_factory=list, max_length=6)
    risks: list[str] = Field(default_factory=list, max_length=6)
    confidence: str = Field(default="medium", pattern="^(low|medium|high)$")
    proposed_activities: list[AIProposedActivity] = Field(default_factory=list, max_length=10)


class AIActivityApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100)
    activities: list[AIProposedActivity] = Field(min_length=1, max_length=10)


class AIExceptionReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str = Field(pattern="^(open|dismissed|corrected|unclear|acted_on)$")
    reason: str = Field(min_length=2, max_length=500)


class AIRankPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occurrence_ids: list[str] = Field(min_length=1, max_length=50)


class AIRankItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(min_length=12, max_length=80)
    rationale: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=1000)
    intent: str = Field(default="quote_follow_up", pattern="^(quote_follow_up|confirm_validity|resolve_missing_validity)$")


class AIRankResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ranked: list[AIRankItem] = Field(min_length=1, max_length=50)


class ApexAssistantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1500)
    resource: str | None = Field(default=None, max_length=50)
    record_id: int | None = Field(default=None, ge=1)


class ApexSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource: str = Field(min_length=2, max_length=50)
    record_id: int = Field(ge=1)


class ApexScoringPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_ids: list[int] | None = Field(default=None, max_length=100)
    persist: bool = False


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

__all__ = [
    "RecordPayload",
    "SettingsPayload",
    "AIProposedActivity",
    "AIChatPayload",
    "AIInsight",
    "AIActivityApprovalPayload",
    "AIExceptionReviewPayload",
    "AIRankPayload",
    "AIRankItem",
    "AIRankResponse",
    "ApexAssistantPayload",
    "ApexSummaryPayload",
    "ApexScoringPayload",
    "BulkArchivePayload",
    "PlatformPayload",
    "RestorePayload"
]
