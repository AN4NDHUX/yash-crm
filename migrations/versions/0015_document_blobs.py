"""Store uploaded document bytes in the database for durable tenant-safe delivery."""
from alembic import op
import sqlalchemy as sa

revision = "0015_document_blobs"
down_revision = "0014_owner_console"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_blobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("platform_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=220), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=False, server_default="application/octet-stream"),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("record_id", name="uq_document_blobs_record_id"),
    )
    op.create_index("ix_document_blobs_record_id", "document_blobs", ["record_id"], unique=True)
    op.create_index("ix_document_blobs_owner_id", "document_blobs", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_blobs_owner_id", table_name="document_blobs")
    op.drop_index("ix_document_blobs_record_id", table_name="document_blobs")
    op.drop_table("document_blobs")
