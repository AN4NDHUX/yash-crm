"""Move owner-aware CRM data to organization tenancy and add invitations.

Revision ID: 0021_organization_record_tenancy
Revises: 0020_organization_subscriptions
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_organization_record_tenancy"
down_revision = "0020_organization_subscriptions"
branch_labels = None
depends_on = None

OWNER_TABLES = [
    "teamspaces",
    "metadata_modules",
    "workflow_executions",
    "leads",
    "accounts",
    "contacts",
    "deals",
    "products",
    "notes",
    "attachments",
    "emails",
    "activities",
    "organization_settings",
    "approval_requests",
    "platform_records",
    "document_blobs",
    "ai_exception_occurrences",
    "ai_task_proposals",
    "import_jobs",
]


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(180), nullable=False),
        sa.Column("membership_role", sa.String(30), nullable=False, server_default="Member"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_organization_invitations_token_hash"),
    )
    op.create_index("ix_organization_invitations_organization_id", "organization_invitations", ["organization_id"])
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"])
    op.create_index("ix_organization_invitations_token_hash", "organization_invitations", ["token_hash"], unique=True)
    op.create_index("ix_organization_invitations_invited_by", "organization_invitations", ["invited_by"])
    op.create_index("ix_organization_invitations_status", "organization_invitations", ["status"])
    op.create_index("ix_organization_invitations_expires_at", "organization_invitations", ["expires_at"])

    for table in OWNER_TABLES:
        op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_organization",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"], unique=False)

    op.add_column("apex_assistant_runs", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_apex_assistant_runs_organization",
        "apex_assistant_runs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_apex_assistant_runs_organization_id", "apex_assistant_runs", ["organization_id"], unique=False)

    # Backfill owner-aware records through the user's active organization membership.
    bind = op.get_bind()
    for table in OWNER_TABLES:
        bind.execute(sa.text(f"""
            UPDATE {table} AS target
            SET organization_id = membership.organization_id
            FROM organization_members AS membership
            WHERE target.owner_id = membership.user_id
              AND membership.status = 'Active'
              AND target.organization_id IS NULL
        """))

    bind.execute(sa.text("""
        UPDATE apex_assistant_runs AS target
        SET organization_id = membership.organization_id
        FROM organization_members AS membership
        WHERE target.requested_by = membership.user_id
          AND membership.status = 'Active'
          AND target.organization_id IS NULL
    """))


def downgrade() -> None:
    op.drop_index("ix_apex_assistant_runs_organization_id", table_name="apex_assistant_runs")
    op.drop_constraint("fk_apex_assistant_runs_organization", "apex_assistant_runs", type_="foreignkey")
    op.drop_column("apex_assistant_runs", "organization_id")

    for table in reversed(OWNER_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization", table, type_="foreignkey")
        op.drop_column(table, "organization_id")

    op.drop_index("ix_organization_invitations_expires_at", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_status", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_invited_by", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_token_hash", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_email", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_organization_id", table_name="organization_invitations")
    op.drop_table("organization_invitations")
