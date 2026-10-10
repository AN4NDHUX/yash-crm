"""Store deal phone number to support mandatory phone mapping for guided imports."""
from alembic import op
import sqlalchemy as sa

revision = "0027_deal_phone_import"
down_revision = "0026_visual_blueprints"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deals", sa.Column("phone", sa.String(40), nullable=True))


def downgrade():
    op.drop_column("deals", "phone")
