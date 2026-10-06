"""Add workflow execution and Blueprint transition history."""
from alembic import op
import sqlalchemy as sa

revision = "0006_workflow_blueprint_engines"
down_revision = "0005_metadata_security_foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("platform_records.id"), nullable=False),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("scheduled_for", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_workflow_execution_key"),
    )
    op.create_index("ix_workflow_executions_rule_id", "workflow_executions", ["rule_id"])
    op.create_index("ix_workflow_executions_record_id", "workflow_executions", ["record_id"])
    op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])
    op.create_index("ix_workflow_executions_scheduled_for", "workflow_executions", ["scheduled_for"])
    op.create_table(
        "blueprint_transition_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("blueprints.id"), nullable=False),
        sa.Column("module", sa.String(80), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("from_stage", sa.String(100), nullable=False),
        sa.Column("to_stage", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_blueprint_transition_logs_blueprint_id", "blueprint_transition_logs", ["blueprint_id"])
    op.create_index("ix_blueprint_transition_logs_record_id", "blueprint_transition_logs", ["record_id"])
    op.create_index("ix_blueprint_transition_logs_created_at", "blueprint_transition_logs", ["created_at"])


def downgrade() -> None:
    for name in ("ix_blueprint_transition_logs_created_at", "ix_blueprint_transition_logs_record_id", "ix_blueprint_transition_logs_blueprint_id"):
        op.drop_index(name, table_name="blueprint_transition_logs")
    op.drop_table("blueprint_transition_logs")
    for name in ("ix_workflow_executions_scheduled_for", "ix_workflow_executions_status", "ix_workflow_executions_record_id", "ix_workflow_executions_rule_id"):
        op.drop_index(name, table_name="workflow_executions")
    op.drop_table("workflow_executions")
