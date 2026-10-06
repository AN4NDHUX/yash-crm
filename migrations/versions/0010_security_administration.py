"""Add full security and administration foundations for Parts 12 and 13."""
from alembic import op
import sqlalchemy as sa

revision = "0010_security_administration"
down_revision = "0009_apex_assistant"
branch_labels = None
depends_on = None


def timestamps():
    return sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False)


def upgrade() -> None:
    for column in (
        sa.Column("profile_name", sa.String(120), nullable=True),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("team", sa.String(120), nullable=True),
        sa.Column("territory_id", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(80), nullable=True),
        sa.Column("language", sa.String(40), nullable=True),
        sa.Column("invited_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("consent_status", sa.String(30), nullable=False, server_default="Unknown"),
        sa.Column("personal_data_classification", sa.String(30), nullable=False, server_default="Normal"),
        sa.Column("sensitive_data", sa.JSON(), nullable=True),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(), nullable=True),
    ):
        op.add_column("users", column)

    op.create_table(
        "territories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.String(40), nullable=False),
        sa.Column("forecasting", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_territory_name"),
    )
    op.create_index("ix_territories_manager_id", "territories", ["manager_id"])
    op.create_table(
        "security_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("group_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_security_group_name"),
    )
    op.create_table(
        "security_group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("security_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membership_role", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("group_id", "user_id", name="uq_security_group_member"),
    )
    op.create_index("ix_security_group_members_group_id", "security_group_members", ["group_id"])
    op.create_index("ix_security_group_members_user_id", "security_group_members", ["user_id"])
    op.create_table(
        "login_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_login_history_user_id", "login_history", ["user_id"])
    op.create_index("ix_login_history_occurred_at", "login_history", ["occurred_at"])
    op.create_table(
        "privacy_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("consent_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("retention_until", sa.DateTime()),
        sa.Column("anonymized_at", sa.DateTime()),
        sa.Column("source", sa.String(80)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_privacy_records_subject", "privacy_records", ["subject_type", "subject_id"])
    op.create_table(
        "ownership_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        *timestamps(),
    )


def downgrade() -> None:
    op.drop_table("ownership_transfers")
    op.drop_index("ix_privacy_records_subject", table_name="privacy_records")
    op.drop_table("privacy_records")
    op.drop_index("ix_login_history_occurred_at", table_name="login_history")
    op.drop_index("ix_login_history_user_id", table_name="login_history")
    op.drop_table("login_history")
    op.drop_index("ix_security_group_members_user_id", table_name="security_group_members")
    op.drop_index("ix_security_group_members_group_id", table_name="security_group_members")
    op.drop_table("security_group_members")
    op.drop_table("security_groups")
    op.drop_index("ix_territories_manager_id", table_name="territories")
    op.drop_table("territories")
    for column in ("anonymized_at", "retention_until", "sensitive_data", "personal_data_classification", "consent_status", "last_login_at", "invited_at", "language", "timezone", "territory_id", "team", "manager_id", "profile_name"):
        op.drop_column("users", column)
