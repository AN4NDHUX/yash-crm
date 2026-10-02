"""Add extensible modules, audit history and import job foundations."""

from alembic import op
import sqlalchemy as sa


revision = "0002_platform_foundations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id")),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id")),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id")),
        sa.Column("related_type", sa.String(80)),
        sa.Column("related_id", sa.Integer()),
        sa.Column("amount", sa.Float()),
        sa.Column("due_date", sa.Date()),
        sa.Column("data", sa.JSON()),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_platform_records_resource", "platform_records", ["resource"])
    op.create_index("ix_platform_records_title", "platform_records", ["title"])
    op.create_index("ix_platform_records_status", "platform_records", ["status"])
    op.create_index("ix_platform_records_owner_id", "platform_records", ["owner_id"])
    op.create_index("ix_platform_records_account_id", "platform_records", ["account_id"])
    op.create_index("ix_platform_records_contact_id", "platform_records", ["contact_id"])
    op.create_index("ix_platform_records_deal_id", "platform_records", ["deal_id"])
    op.create_index("ix_platform_records_archived", "platform_records", ["archived"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("record_id", sa.Integer()),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("before", sa.JSON()),
        sa.Column("after", sa.JSON()),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_resource", "audit_events", ["resource"])

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource", sa.String(80), nullable=False),
        sa.Column("filename", sa.String(220), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_import_jobs_resource", "import_jobs", ["resource"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_resource", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    for name in ("ix_platform_records_archived", "ix_platform_records_deal_id", "ix_platform_records_contact_id", "ix_platform_records_account_id", "ix_platform_records_owner_id", "ix_platform_records_status", "ix_platform_records_title", "ix_platform_records_resource"):
        op.drop_index(name, table_name="platform_records")
    op.drop_table("platform_records")
