"""Repair notification storage for production databases with schema drift."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0019_repair_notifications"
down_revision = "0018_remove_login_otp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False, server_default="info"),
            sa.Column("title", sa.String(length=220), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("resource", sa.String(length=80), nullable=True),
            sa.Column("record_id", sa.Integer(), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("notifications")}
        additions = [
            ("kind", sa.Column("kind", sa.String(length=40), nullable=False, server_default="info")),
            ("title", sa.Column("title", sa.String(length=220), nullable=False, server_default="Notification")),
            ("body", sa.Column("body", sa.Text(), nullable=True)),
            ("resource", sa.Column("resource", sa.String(length=80), nullable=True)),
            ("record_id", sa.Column("record_id", sa.Integer(), nullable=True)),
            ("read_at", sa.Column("read_at", sa.DateTime(), nullable=True)),
            ("created_at", sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))),
        ]
        for name, column in additions:
            if name not in columns:
                op.add_column("notifications", column)

    inspector = inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("notifications")}
    if "ix_notifications_user_id" not in existing_indexes:
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    if "ix_notifications_read_at" not in existing_indexes:
        op.create_index("ix_notifications_read_at", "notifications", ["read_at"], unique=False)
    if "ix_notifications_created_at" not in existing_indexes:
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)


def downgrade() -> None:
    # Repair migrations are intentionally non-destructive on downgrade.
    pass
