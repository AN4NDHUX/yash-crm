"""Add grounded APEX assistant request history."""
from alembic import op
import sqlalchemy as sa

revision = "0009_apex_assistant"
down_revision = "0008_report_dashboard_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apex_assistant_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question", sa.String(1500), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_apex_assistant_runs_intent", "apex_assistant_runs", ["intent"])
    op.create_index("ix_apex_assistant_runs_created_at", "apex_assistant_runs", ["created_at"])
    op.create_index("ix_apex_assistant_runs_requested_by", "apex_assistant_runs", ["requested_by"])


def downgrade() -> None:
    for name in ("ix_apex_assistant_runs_requested_by", "ix_apex_assistant_runs_created_at", "ix_apex_assistant_runs_intent"):
        op.drop_index(name, table_name="apex_assistant_runs")
    op.drop_table("apex_assistant_runs")
