"""Soft delete retained setup configurations.

Revision ID: 0025_recyclable_config
Revises: 0024_workflow_delivery_queue
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_recyclable_config"
down_revision = "0024_workflow_delivery_queue"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("approval_processes", "blueprints"):
        op.add_column(table, sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index(f"ix_{table}_archived", table, ["archived"])
    op.add_column("blueprints", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE blueprints SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")


def downgrade():
    op.drop_column("blueprints", "updated_at")
    for table in ("blueprints", "approval_processes"):
        op.drop_index(f"ix_{table}_archived", table_name=table)
        op.drop_column(table, "archived")
