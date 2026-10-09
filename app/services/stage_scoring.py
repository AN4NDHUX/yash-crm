"""Deterministic stage scoring policy for Leads and Deals.

Probability is a forecast estimate, not the engagement score. This module
contains no database access; callers must apply organization-scoped policy.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LEAD_STAGES = (
    ("New", 5, 5, "Open", "Pipeline"),
    ("Contacted", 15, 15, "Open", "Pipeline"),
    ("Qualified", 35, 35, "Open", "Pipeline"),
    ("Site Visit Scheduled", 45, 45, "Open", "Pipeline"),
    ("Site Visit Completed", 60, 60, "Open", "Pipeline"),
    ("Proposal Sent", 65, 65, "Open", "Pipeline"),
    ("Pricing Negotiation", 75, 75, "Open", "Pipeline"),
    ("Final Approval", 90, 90, "Open", "Committed"),
    ("Converted", 100, 100, "Closed Won", "Closed"),
    ("Unqualified", 0, 0, "Closed Lost", "Omitted"),
)
RECORD_CATEGORIES = frozenset(("Open", "Closed Won", "Closed Lost"))
FORECAST_CATEGORIES = frozenset(("Pipeline", "Best Case", "Committed", "Closed", "Omitted"))


@dataclass(frozen=True)
class StageMapping:
    name: str
    probability: int
    stage_score: int
    record_category: str
    forecast_category: str


def validate_mapping(rows: list[dict]) -> tuple[StageMapping, ...]:
    """Validate an administrator-supplied mapping before persistence."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 40:
        raise ValueError("Stage mapping must contain 1 to 40 stages")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Stage mapping rows must be objects")
        name = row.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Stage name must contain 1 to 80 characters")
        name = name.strip()
        if name.casefold() in seen:
            raise ValueError("Duplicate stage name")
        seen.add(name.casefold())
        probability, score = row.get("probability"), row.get("stage_score")
        if type(probability) is not int or not 0 <= probability <= 100:
            raise ValueError("Probability must be an integer from 0 to 100")
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("Stage score must be an integer from 0 to 100")
        category = row.get("record_category")
        forecast = row.get("forecast_category")
        if category not in RECORD_CATEGORIES or forecast not in FORECAST_CATEGORIES:
            raise ValueError("Invalid record or forecast category")
        if category == "Closed Won" and (probability != 100 or forecast != "Closed"):
            raise ValueError("Closed Won requires 100% probability and Closed forecast")
        if category == "Closed Lost" and (probability != 0 or forecast != "Omitted"):
            raise ValueError("Closed Lost requires 0% probability and Omitted forecast")
        result.append(StageMapping(name, probability, score, category, forecast))
    return tuple(result)


def default_mapping() -> tuple[StageMapping, ...]:
    return tuple(StageMapping(*row) for row in DEFAULT_LEAD_STAGES)


def score_transition(current: str, target: str, mapping: tuple[StageMapping, ...],
                     engagement_score: int = 0) -> dict:
    """Calculate a transition without side effects or double-counting.

    The engagement score is independent of the stage score and must be
    recomputed from signals by its owning scoring engine.
    """
    if type(engagement_score) is not int or not 0 <= engagement_score <= 100:
        raise ValueError("Engagement score must be between 0 and 100")
    stages = {stage.name: stage for stage in mapping}
    if target not in stages:
        raise ValueError("Unknown destination stage")
    stage = stages[target]
    return {
        "from_stage": current,
        "to_stage": target,
        "changed": current != target,
        "stage_score": stage.stage_score,
        "engagement_score": engagement_score,
        "probability": stage.probability,
        "record_category": stage.record_category,
        "forecast_category": stage.forecast_category,
    }
