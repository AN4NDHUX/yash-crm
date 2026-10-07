"""Tenant-scope security/configuration tables and uniqueness.

Revision ID: 0023_tenant_security_configuration
Revises: 0022_billing_webhook_events
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_tenant_security_configuration"
down_revision = "0022_billing_webhook_events"
branch_labels = None
depends_on = None

TABLES = [
    "territories",
    "security_groups",
    "permission_profiles",
    "sharing_policies",
    "approval_processes",
    "blueprints",
    "blueprint_transition_logs",
    "report_runs",
    "audit_events",
    "privacy_records",
    "ownership_transfers",
    "api_request_logs",
    "ai_exception_events",
    "ai_task_operations",
]


def _add_org_column(table: str) -> None:
    op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        f"fk_{table}_organization",
        table,
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"], unique=False)


def upgrade() -> None:
    for table in TABLES:
        _add_org_column(table)

    # Global uniqueness is invalid in a multi-organization SaaS model.
    op.drop_constraint("uq_territory_name", "territories", type_="unique")
    op.drop_constraint("uq_security_group_name", "security_groups", type_="unique")
    op.drop_constraint("uq_permission_profile_name", "permission_profiles", type_="unique")
    op.drop_constraint("uq_metadata_module_api_name", "metadata_modules", type_="unique")

    op.create_unique_constraint("uq_territory_org_name", "territories", ["organization_id", "name"])
    op.create_unique_constraint("uq_security_group_org_name", "security_groups", ["organization_id", "name"])
    op.create_unique_constraint("uq_permission_profile_org_name", "permission_profiles", ["organization_id", "name"])
    op.create_unique_constraint("uq_metadata_module_org_api_name", "metadata_modules", ["organization_id", "api_name"])

    bind = op.get_bind()
    first_org = bind.execute(sa.text("SELECT id FROM organizations ORDER BY id LIMIT 1")).scalar()

    actor_backfills = {
        "blueprint_transition_logs": "actor_id",
        "report_runs": "requested_by",
        "audit_events": "actor_id",
        "privacy_records": "user_id",
        "ownership_transfers": "requested_by",
        "api_request_logs": "actor_id",
        "ai_exception_events": "actor_id",
    }
    for table, user_column in actor_backfills.items():
        bind.execute(sa.text(f"""
            UPDATE {table} AS target
            SET organization_id = membership.organization_id
            FROM organization_members AS membership
            WHERE target.{user_column} = membership.user_id
              AND membership.status = 'Active'
              AND target.organization_id IS NULL
        """))

    bind.execute(sa.text("""
        UPDATE ai_task_operations AS target
        SET organization_id = proposal.organization_id
        FROM ai_task_proposals AS proposal
        WHERE target.proposal_id = proposal.id
          AND target.organization_id IS NULL
    """))

    bind.execute(sa.text("""
        UPDATE territories AS target
        SET organization_id = membership.organization_id
        FROM organization_members AS membership
        WHERE target.manager_id = membership.user_id
          AND membership.status = 'Active'
          AND target.organization_id IS NULL
    """))

    # Legacy configuration had no tenant key. Assign it to the first existing
    # organization (normally the platform owner's workspace) rather than leaking it.
    if first_org is not None:
        for table in (
            "territories",
            "security_groups",
            "permission_profiles",
            "sharing_policies",
            "approval_processes",
            "blueprints",
            "blueprint_transition_logs",
            "report_runs",
            "audit_events",
            "privacy_records",
            "ownership_transfers",
            "api_request_logs",
            "ai_exception_events",
            "ai_task_operations",
        ):
            bind.execute(
                sa.text(f"UPDATE {table} SET organization_id = :org WHERE organization_id IS NULL"),
                {"org": first_org},
            )


def downgrade() -> None:
    op.drop_constraint("uq_metadata_module_org_api_name", "metadata_modules", type_="unique")
    op.drop_constraint("uq_permission_profile_org_name", "permission_profiles", type_="unique")
    op.drop_constraint("uq_security_group_org_name", "security_groups", type_="unique")
    op.drop_constraint("uq_territory_org_name", "territories", type_="unique")

    op.create_unique_constraint("uq_metadata_module_api_name", "metadata_modules", ["api_name"])
    op.create_unique_constraint("uq_permission_profile_name", "permission_profiles", ["name"])
    op.create_unique_constraint("uq_security_group_name", "security_groups", ["name"])
    op.create_unique_constraint("uq_territory_name", "territories", ["name"])

    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
