"""Scope organization settings to the authenticated CRM workspace."""
from alembic import op
import sqlalchemy as sa

revision = "0013_user_workspace_settings"
down_revision = "0012_user_tenant_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organization_settings", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_organization_settings_owner",
        "organization_settings",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_organization_settings_owner_id", "organization_settings", ["owner_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organization_settings_owner_id", table_name="organization_settings")
    op.drop_constraint("fk_organization_settings_owner", "organization_settings", type_="foreignkey")
    op.drop_column("organization_settings", "owner_id")
