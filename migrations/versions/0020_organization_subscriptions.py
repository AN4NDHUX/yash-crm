"""Introduce organization-owned subscriptions and safe upgrade requests.

Revision ID: 0020_organization_subscriptions
Revises: 0019_repair_notifications
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_organization_subscriptions"
down_revision = "0019_repair_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Active"),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_status", "organizations", ["status"], unique=False)
    op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"], unique=False)

    op.create_table(
        "organization_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membership_role", sa.String(30), nullable=False, server_default="Member"),
        sa.Column("status", sa.String(30), nullable=False, server_default="Active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"], unique=False)
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"], unique=False)
    op.create_index("ix_organization_members_status", "organization_members", ["status"], unique=False)

    op.create_table(
        "organization_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Active"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(60), nullable=True),
        sa.Column("provider_customer_id", sa.String(180), nullable=True),
        sa.Column("provider_subscription_id", sa.String(180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_organization_subscriptions_organization_id"),
    )
    op.create_index("ix_organization_subscriptions_organization_id", "organization_subscriptions", ["organization_id"], unique=True)
    op.create_index("ix_organization_subscriptions_plan_id", "organization_subscriptions", ["plan_id"], unique=False)
    op.create_index("ix_organization_subscriptions_status", "organization_subscriptions", ["status"], unique=False)

    op.create_table(
        "subscription_change_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("to_plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Pending Payment"),
        sa.Column("provider", sa.String(60), nullable=True),
        sa.Column("provider_reference", sa.String(180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_subscription_change_requests_organization_id", "subscription_change_requests", ["organization_id"], unique=False)
    op.create_index("ix_subscription_change_requests_requested_by", "subscription_change_requests", ["requested_by"], unique=False)
    op.create_index("ix_subscription_change_requests_to_plan_id", "subscription_change_requests", ["to_plan_id"], unique=False)
    op.create_index("ix_subscription_change_requests_status", "subscription_change_requests", ["status"], unique=False)
    op.create_index("ix_subscription_change_requests_provider_reference", "subscription_change_requests", ["provider_reference"], unique=False)

    bind = op.get_bind()
    now = sa.func.now()

    users = bind.execute(sa.text("SELECT id, name, username FROM users ORDER BY id")).mappings().all()
    free_plan_id = bind.execute(sa.text("SELECT id FROM plans WHERE lower(code) = 'free' ORDER BY id LIMIT 1")).scalar()

    for user in users:
        user_id = int(user["id"])
        name = str(user.get("name") or user.get("username") or f"Workspace {user_id}")[:160]
        slug = f"workspace-{user_id}"

        organization_id = bind.execute(
            sa.text(
                "INSERT INTO organizations (name, slug, status, owner_user_id, created_at, updated_at) "
                "VALUES (:name, :slug, 'Active', :user_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "RETURNING id"
            ),
            {"name": name, "slug": slug, "user_id": user_id},
        ).scalar_one()

        bind.execute(
            sa.text(
                "INSERT INTO organization_members "
                "(organization_id, user_id, membership_role, status, created_at, updated_at) "
                "VALUES (:organization_id, :user_id, 'Owner', 'Active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"organization_id": organization_id, "user_id": user_id},
        )

        legacy = bind.execute(
            sa.text(
                "SELECT plan_id, status, started_at, trial_ends_at, current_period_start, current_period_end, "
                "cancel_at_period_end, provider, provider_customer_id, provider_subscription_id "
                "FROM subscriptions WHERE user_id = :user_id ORDER BY id LIMIT 1"
            ),
            {"user_id": user_id},
        ).mappings().first()

        plan_id = int(legacy["plan_id"]) if legacy and legacy.get("plan_id") is not None else free_plan_id
        if plan_id is None:
            continue

        bind.execute(
            sa.text(
                "INSERT INTO organization_subscriptions "
                "(organization_id, plan_id, status, started_at, trial_ends_at, current_period_start, current_period_end, "
                "cancel_at_period_end, provider, provider_customer_id, provider_subscription_id, created_at, updated_at) "
                "VALUES (:organization_id, :plan_id, :status, COALESCE(:started_at, CURRENT_TIMESTAMP), :trial_ends_at, "
                ":current_period_start, :current_period_end, :cancel_at_period_end, :provider, :provider_customer_id, "
                ":provider_subscription_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "organization_id": organization_id,
                "plan_id": plan_id,
                "status": str(legacy["status"] if legacy else "Active"),
                "started_at": legacy["started_at"] if legacy else None,
                "trial_ends_at": legacy["trial_ends_at"] if legacy else None,
                "current_period_start": legacy["current_period_start"] if legacy else None,
                "current_period_end": legacy["current_period_end"] if legacy else None,
                "cancel_at_period_end": bool(legacy["cancel_at_period_end"]) if legacy else False,
                "provider": legacy["provider"] if legacy else None,
                "provider_customer_id": legacy["provider_customer_id"] if legacy else None,
                "provider_subscription_id": legacy["provider_subscription_id"] if legacy else None,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_subscription_change_requests_provider_reference", table_name="subscription_change_requests")
    op.drop_index("ix_subscription_change_requests_status", table_name="subscription_change_requests")
    op.drop_index("ix_subscription_change_requests_to_plan_id", table_name="subscription_change_requests")
    op.drop_index("ix_subscription_change_requests_requested_by", table_name="subscription_change_requests")
    op.drop_index("ix_subscription_change_requests_organization_id", table_name="subscription_change_requests")
    op.drop_table("subscription_change_requests")

    op.drop_index("ix_organization_subscriptions_status", table_name="organization_subscriptions")
    op.drop_index("ix_organization_subscriptions_plan_id", table_name="organization_subscriptions")
    op.drop_index("ix_organization_subscriptions_organization_id", table_name="organization_subscriptions")
    op.drop_table("organization_subscriptions")

    op.drop_index("ix_organization_members_status", table_name="organization_members")
    op.drop_index("ix_organization_members_user_id", table_name="organization_members")
    op.drop_index("ix_organization_members_organization_id", table_name="organization_members")
    op.drop_table("organization_members")

    op.drop_index("ix_organizations_owner_user_id", table_name="organizations")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
