"""Visual Blueprint designer metadata and record layout matching.

Revision ID: 0026_visual_blueprints
Revises: 0025_recyclable_config
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_visual_blueprints"
down_revision = "0025_recyclable_config"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("layout_name", sa.String(100), nullable=False, server_default="Default"))
    op.add_column("deals", sa.Column("layout_name", sa.String(100), nullable=False, server_default="Default"))
    op.add_column("blueprints", sa.Column("layout_name", sa.String(100), nullable=False, server_default="Default"))
    op.add_column("blueprints", sa.Column("field_name", sa.String(80), nullable=False, server_default="status"))
    op.add_column("blueprints", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("blueprints", sa.Column("entry_conditions", sa.JSON(), nullable=True))
    op.add_column("blueprints", sa.Column("draft", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("blueprints", sa.Column("continuous", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE blueprints SET field_name = 'stage' WHERE lower(module) IN ('deal', 'deals')")


def downgrade():
    for field in ("continuous", "draft", "entry_conditions", "description", "field_name", "layout_name"):
        op.drop_column("blueprints", field)
    op.drop_column("deals", "layout_name")
    op.drop_column("leads", "layout_name")
