"""Durable workflow worker leases and retries.

Revision ID: 0024_workflow_delivery_queue
Revises: 0023_tenant_security_configuration
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_workflow_delivery_queue"
down_revision = "0023_tenant_security_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_executions", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("workflow_executions", sa.Column("locked_at", sa.DateTime(), nullable=True))
    op.add_column("workflow_executions", sa.Column("next_attempt_at", sa.DateTime(), nullable=True))
    op.create_index("ix_workflow_due_status", "workflow_executions", ["status", "scheduled_for", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_due_status", table_name="workflow_executions")
    op.drop_column("workflow_executions", "next_attempt_at")
    op.drop_column("workflow_executions", "locked_at")
    op.drop_column("workflow_executions", "attempts")
