"""Add deterministic AI revenue exception and approval foundations."""

from alembic import op
import sqlalchemy as sa


revision = "0003_ai_revenue_exceptions"
down_revision = "0002_platform_foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("platform_records", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    op.create_table(
        "ai_exception_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(80), nullable=False),
        sa.Column("source_resource", sa.String(80), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("trigger_kind", sa.String(50), nullable=False),
        sa.Column("review_state", sa.String(30), nullable=False),
        sa.Column("active_key", sa.String(180)),
        sa.Column("predecessor_id", sa.Integer(), sa.ForeignKey("ai_exception_occurrences.id")),
        sa.Column("dismissed_until", sa.DateTime()),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("facts", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("active_key", name="uq_ai_exception_active_key"),
    )
    op.create_index("ix_ai_exception_occurrences_public_id", "ai_exception_occurrences", ["public_id"], unique=True)
    for name, columns in (
        ("ix_ai_exception_occurrences_rule_version", ["rule_version"]),
        ("ix_ai_exception_occurrences_source_id", ["source_id"]),
        ("ix_ai_exception_occurrences_trigger_kind", ["trigger_kind"]),
        ("ix_ai_exception_occurrences_review_state", ["review_state"]),
    ):
        op.create_index(name, "ai_exception_occurrences", columns)

    op.create_table(
        "ai_exception_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurrence_id", sa.Integer(), sa.ForeignKey("ai_exception_occurrences.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("from_state", sa.String(30)),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("rule_version", sa.String(80), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_exception_events_occurrence_id", "ai_exception_events", ["occurrence_id"])
    op.create_index("ix_ai_exception_events_occurred_at", "ai_exception_events", ["occurred_at"])

    op.create_table(
        "ai_task_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), sa.ForeignKey("ai_exception_occurrences.id"), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("intent_code", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("operation_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id")),
        sa.Column("provider", sa.String(120)),
        sa.Column("model", sa.String(180)),
        sa.Column("provider_request_id", sa.String(180)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("public_id", "version", name="uq_ai_task_proposal_version"),
    )
    for name, columns in (
        ("ix_ai_task_proposals_public_id", ["public_id"]),
        ("ix_ai_task_proposals_occurrence_id", ["occurrence_id"]),
        ("ix_ai_task_proposals_operation_key", ["operation_key"]),
        ("ix_ai_task_proposals_status", ["status"]),
    ):
        op.create_index(name, "ai_task_proposals", columns)

    op.create_table(
        "ai_task_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_key", sa.String(64), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("ai_task_proposals.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_task_operations_operation_key", "ai_task_operations", ["operation_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ai_task_operations_operation_key", table_name="ai_task_operations")
    op.drop_table("ai_task_operations")
    for name in ("ix_ai_task_proposals_status", "ix_ai_task_proposals_operation_key", "ix_ai_task_proposals_occurrence_id", "ix_ai_task_proposals_public_id"):
        op.drop_index(name, table_name="ai_task_proposals")
    op.drop_table("ai_task_proposals")
    op.drop_index("ix_ai_exception_events_occurred_at", table_name="ai_exception_events")
    op.drop_index("ix_ai_exception_events_occurrence_id", table_name="ai_exception_events")
    op.drop_table("ai_exception_events")
    for name in ("ix_ai_exception_occurrences_review_state", "ix_ai_exception_occurrences_trigger_kind", "ix_ai_exception_occurrences_source_id", "ix_ai_exception_occurrences_rule_version", "ix_ai_exception_occurrences_public_id"):
        op.drop_index(name, table_name="ai_exception_occurrences")
    op.drop_table("ai_exception_occurrences")
    op.drop_column("platform_records", "version")
