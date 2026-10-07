"""Remove deferred one-time login OTP storage."""
from alembic import op
import sqlalchemy as sa

revision = "0018_remove_login_otp"
down_revision = "0017_login_otp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_login_otp_challenges_used_at", table_name="login_otp_challenges")
    op.drop_index("ix_login_otp_challenges_expires_at", table_name="login_otp_challenges")
    op.drop_index("ix_login_otp_challenges_user_id", table_name="login_otp_challenges")
    op.drop_index("ix_login_otp_challenges_public_id", table_name="login_otp_challenges")
    op.drop_table("login_otp_challenges")


def downgrade() -> None:
    op.create_table(
        "login_otp_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("otp_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.UniqueConstraint("public_id", name="uq_login_otp_challenges_public_id"),
    )
    op.create_index("ix_login_otp_challenges_public_id", "login_otp_challenges", ["public_id"], unique=True)
    op.create_index("ix_login_otp_challenges_user_id", "login_otp_challenges", ["user_id"], unique=False)
    op.create_index("ix_login_otp_challenges_expires_at", "login_otp_challenges", ["expires_at"], unique=False)
    op.create_index("ix_login_otp_challenges_used_at", "login_otp_challenges", ["used_at"], unique=False)
