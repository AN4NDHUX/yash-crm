"""Add user tenancy, login identifiers, and password-reset tokens."""
from alembic import op
import sqlalchemy as sa

revision = "0012_user_tenant_auth"
down_revision = "0011_account_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(40), nullable=True))
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])

    op.add_column("metadata_modules", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_metadata_modules_owner", "metadata_modules", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_metadata_modules_owner_id", "metadata_modules", ["owner_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_metadata_modules_owner_id", table_name="metadata_modules")
    op.drop_constraint("fk_metadata_modules_owner", "metadata_modules", type_="foreignkey")
    op.drop_column("metadata_modules", "owner_id")
    op.drop_constraint("uq_users_phone", "users", type_="unique")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "phone")
    op.drop_column("users", "username")
