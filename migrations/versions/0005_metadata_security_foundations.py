"""Add metadata-driven customization and security foundation tables."""
from alembic import op
import sqlalchemy as sa

revision = "0005_metadata_security_foundations"
down_revision = "0004_enterprise_collaboration_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metadata_modules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_name", sa.String(100), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("plural_label", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("api_name", name="uq_metadata_module_api_name"),
    )
    op.create_index("ix_metadata_modules_enabled", "metadata_modules", ["enabled"])
    op.create_table(
        "metadata_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("metadata_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_name", sa.String(100), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("field_type", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unique_value", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_value", sa.JSON()),
        sa.Column("validation", sa.JSON()),
        sa.Column("permissions", sa.JSON()),
        sa.Column("visibility", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("module_id", "api_name", name="uq_metadata_field_api_name"),
    )
    op.create_index("ix_metadata_fields_module_id", "metadata_fields", ["module_id"])
    op.create_table(
        "metadata_layouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("metadata_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("assignment", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_metadata_layouts_module_id", "metadata_layouts", ["module_id"])
    op.create_table(
        "metadata_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("metadata_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("sorting", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_metadata_views_module_id", "metadata_views", ["module_id"])
    op.create_table(
        "permission_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("grants", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_permission_profile_name"),
    )
    op.create_table(
        "sharing_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("access", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sharing_policies_module", "sharing_policies", ["module"])


def downgrade() -> None:
    op.drop_index("ix_sharing_policies_module", table_name="sharing_policies")
    op.drop_table("sharing_policies")
    op.drop_table("permission_profiles")
    op.drop_index("ix_metadata_views_module_id", table_name="metadata_views")
    op.drop_table("metadata_views")
    op.drop_index("ix_metadata_layouts_module_id", table_name="metadata_layouts")
    op.drop_table("metadata_layouts")
    op.drop_index("ix_metadata_fields_module_id", table_name="metadata_fields")
    op.drop_table("metadata_fields")
    op.drop_index("ix_metadata_modules_enabled", table_name="metadata_modules")
    op.drop_table("metadata_modules")
