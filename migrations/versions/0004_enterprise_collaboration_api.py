"""Add enterprise collaboration and API foundation tables."""
from alembic import op
import sqlalchemy as sa

revision = "0004_enterprise_collaboration_api"
down_revision = "0003_ai_revenue_exceptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic creates alembic_version.version_num as VARCHAR(32) by default.
    # This revision ID is 33 characters (and 0005 is 34), so PostgreSQL
    # would roll back the migration when Alembic records the new version.
    # Widen the version column before Alembic updates it. SQLite does not
    # enforce VARCHAR lengths, so no change is required there.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(128)"
        )

    op.create_table(
        "teamspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("icon", sa.String(40), nullable=False, server_default="◈"),
        sa.Column("description", sa.Text()),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("folders", sa.JSON(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_teamspaces_owner_id", "teamspaces", ["owner_id"])
    op.create_index("ix_teamspaces_archived", "teamspaces", ["archived"])
    op.create_table(
        "teamspace_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teamspace_id", sa.Integer(), sa.ForeignKey("teamspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membership_role", sa.String(30), nullable=False, server_default="Member"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("teamspace_id", "user_id", name="uq_teamspace_member"),
    )
    op.create_index("ix_teamspace_members_teamspace_id", "teamspace_members", ["teamspace_id"])
    op.create_index("ix_teamspace_members_user_id", "teamspace_members", ["user_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("resource", sa.String(80)),
        sa.Column("record_id", sa.Integer()),
        sa.Column("read_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read_at", "notifications", ["read_at"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_table(
        "api_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("resource", sa.String(80)),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_api_request_logs_created_at", "api_request_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_api_request_logs_created_at", table_name="api_request_logs")
    op.drop_table("api_request_logs")
    for name in ("ix_notifications_created_at", "ix_notifications_read_at", "ix_notifications_user_id"):
        op.drop_index(name, table_name="notifications")
    op.drop_table("notifications")
    for name in ("ix_teamspace_members_user_id", "ix_teamspace_members_teamspace_id"):
        op.drop_index(name, table_name="teamspace_members")
    op.drop_table("teamspace_members")
    for name in ("ix_teamspaces_archived", "ix_teamspaces_owner_id"):
        op.drop_index(name, table_name="teamspaces")
    op.drop_table("teamspaces")
