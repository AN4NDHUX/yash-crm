"""Add idempotent billing webhook events.

Revision ID: 0022_billing_webhook_events
Revises: 0021_organization_record_tenancy
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_billing_webhook_events"
down_revision = "0021_organization_record_tenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("subscription_change_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="Received"),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_key", name="uq_billing_webhook_events_event_key"),
    )
    op.create_index("ix_billing_webhook_events_provider", "billing_webhook_events", ["provider"])
    op.create_index("ix_billing_webhook_events_event_key", "billing_webhook_events", ["event_key"], unique=True)
    op.create_index("ix_billing_webhook_events_request_id", "billing_webhook_events", ["request_id"])
    op.create_index("ix_billing_webhook_events_status", "billing_webhook_events", ["status"])
    op.create_index("ix_billing_webhook_events_received_at", "billing_webhook_events", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_billing_webhook_events_received_at", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_status", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_request_id", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_event_key", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_provider", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")
