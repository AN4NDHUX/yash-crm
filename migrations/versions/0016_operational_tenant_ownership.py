"""Add tenant ownership to operational records."""
from alembic import op
import sqlalchemy as sa

revision = "0016_operational_tenant_ownership"
down_revision = "0015_document_blobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("ai_exception_occurrences", "workflow_executions", "approval_requests", "import_jobs"):
        op.add_column(table, sa.Column("owner_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_owner",
            table,
            "users",
            ["owner_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"], unique=False)

    op.execute(sa.text("""
        UPDATE ai_exception_occurrences AS a
        SET owner_id = p.owner_id
        FROM platform_records AS p
        WHERE a.source_resource = 'quotes'
          AND a.source_id = p.id
          AND p.owner_id IS NOT NULL
    """))
    op.execute(sa.text("""
        UPDATE workflow_executions AS w
        SET owner_id = p.owner_id
        FROM platform_records AS p
        WHERE w.record_id = p.id
          AND p.owner_id IS NOT NULL
    """))
    op.execute(sa.text("""
        UPDATE approval_requests
        SET owner_id = requester_id
        WHERE requester_id IS NOT NULL
    """))


def downgrade() -> None:
    for table in ("import_jobs", "approval_requests", "workflow_executions", "ai_exception_occurrences"):
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_constraint(f"fk_{table}_owner", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
