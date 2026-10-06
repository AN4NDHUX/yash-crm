"""Add report execution history for the metadata-driven Report Engine."""
from alembic import op
import sqlalchemy as sa

revision = "0008_report_dashboard_engine"
down_revision = "0007_approval_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("platform_records.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_report_runs_report_id", "report_runs", ["report_id"])
    op.create_index("ix_report_runs_status", "report_runs", ["status"])
    op.create_index("ix_report_runs_created_at", "report_runs", ["created_at"])


def downgrade() -> None:
    for name in ("ix_report_runs_created_at", "ix_report_runs_status", "ix_report_runs_report_id"):
        op.drop_index(name, table_name="report_runs")
    op.drop_table("report_runs")
