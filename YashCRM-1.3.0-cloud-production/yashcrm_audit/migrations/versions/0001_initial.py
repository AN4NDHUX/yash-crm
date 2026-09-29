"""Initial Yash CRM schema.

The migration is metadata-backed so a clean deployment can create all CRM tables
without relying on a process-local ``create_all`` call. Existing preview data is
upgraded additively by the startup schema guard in ``app.main``.
"""
from alembic import op
from app.main import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
