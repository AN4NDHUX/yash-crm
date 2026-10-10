"""Track converted Deal origin and prevent duplicate conversion Deals."""
from alembic import op
import sqlalchemy as sa

revision = "0028_deal_origin_lead"
down_revision = "0027_deal_phone_import"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("deals", sa.Column("origin_lead_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_deals_origin_lead", "deals", "leads", ["origin_lead_id"], ["id"])
    op.create_index("ix_deals_origin_lead_id", "deals", ["origin_lead_id"], unique=True)


def downgrade():
    op.drop_index("ix_deals_origin_lead_id", table_name="deals")
    op.drop_constraint("fk_deals_origin_lead", "deals", type_="foreignkey")
    op.drop_column("deals", "origin_lead_id")
