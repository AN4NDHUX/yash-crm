"""Add multi-level approval request and decision history."""
from alembic import op
import sqlalchemy as sa

revision = "0007_approval_engine"
down_revision = "0006_workflow_blueprint_engines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("approval_processes.id"), nullable=False),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("comment", sa.Text()),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("operation_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("operation_key", name="uq_approval_request_operation_key"),
    )
    for name, columns in (
        ("ix_approval_requests_process_id", ["process_id"]),
        ("ix_approval_requests_record_id", ["record_id"]),
        ("ix_approval_requests_status", ["status"]),
        ("ix_approval_requests_submitted_at", ["submitted_at"]),
    ):
        op.create_index(name, "approval_requests", columns)
    op.create_table(
        "approval_step_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("approver_label", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("delegated_to", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("acted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", "step_order", name="uq_approval_request_step"),
    )
    op.create_index("ix_approval_step_decisions_request_id", "approval_step_decisions", ["request_id"])
    op.create_index("ix_approval_step_decisions_approver_id", "approval_step_decisions", ["approver_id"])
    op.create_index("ix_approval_step_decisions_status", "approval_step_decisions", ["status"])


def downgrade() -> None:
    for name in ("ix_approval_step_decisions_status", "ix_approval_step_decisions_approver_id", "ix_approval_step_decisions_request_id"):
        op.drop_index(name, table_name="approval_step_decisions")
    op.drop_table("approval_step_decisions")
    for name in ("ix_approval_requests_submitted_at", "ix_approval_requests_status", "ix_approval_requests_record_id", "ix_approval_requests_process_id"):
        op.drop_index(name, table_name="approval_requests")
    op.drop_table("approval_requests")
