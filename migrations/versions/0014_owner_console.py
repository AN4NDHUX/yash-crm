"""Add owner console subscription plans and user subscriptions."""
from alembic import op
import sqlalchemy as sa

revision = "0014_owner_console"
down_revision = "0013_user_workspace_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("price_monthly", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("max_records", sa.Integer(), nullable=True),
        sa.Column("max_storage_mb", sa.Integer(), nullable=True),
        sa.Column("max_custom_modules", sa.Integer(), nullable=True),
        sa.Column("ai_limit_monthly", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)
    op.create_index("ix_plans_active", "plans", ["active"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="Active"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(length=60), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=180), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"], unique=False)
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)

    plans = sa.table(
        "plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("price_monthly", sa.Float),
        sa.column("currency", sa.String),
        sa.column("max_records", sa.Integer),
        sa.column("max_storage_mb", sa.Integer),
        sa.column("max_custom_modules", sa.Integer),
        sa.column("ai_limit_monthly", sa.Integer),
        sa.column("active", sa.Boolean),
        sa.column("features", sa.JSON),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = sa.func.now()
    op.bulk_insert(plans, [
        {"code":"free","name":"Free","price_monthly":0.0,"currency":"USD","max_records":1000,"max_storage_mb":250,"max_custom_modules":2,"ai_limit_monthly":100,"active":True,"features":{"reports":True,"custom_modules":True,"apex":False},"created_at":now,"updated_at":now},
        {"code":"standard","name":"Standard","price_monthly":19.0,"currency":"USD","max_records":10000,"max_storage_mb":2048,"max_custom_modules":10,"ai_limit_monthly":1500,"active":True,"features":{"reports":True,"custom_modules":True,"apex":True},"created_at":now,"updated_at":now},
        {"code":"professional","name":"Professional","price_monthly":49.0,"currency":"USD","max_records":100000,"max_storage_mb":10240,"max_custom_modules":50,"ai_limit_monthly":10000,"active":True,"features":{"reports":True,"custom_modules":True,"apex":True,"advanced_analytics":True},"created_at":now,"updated_at":now},
        {"code":"enterprise","name":"Enterprise","price_monthly":99.0,"currency":"USD","max_records":None,"max_storage_mb":None,"max_custom_modules":None,"ai_limit_monthly":None,"active":True,"features":{"reports":True,"custom_modules":True,"apex":True,"advanced_analytics":True,"priority_support":True},"created_at":now,"updated_at":now},
    ])

    bind = op.get_bind()
    free_id = bind.execute(sa.text("SELECT id FROM plans WHERE code='free'")).scalar()
    bind.execute(sa.text("""
        INSERT INTO subscriptions
            (user_id, plan_id, status, started_at, current_period_start, cancel_at_period_end, created_at, updated_at)
        SELECT id, :plan_id, 'Active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM users
        WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id = users.id)
    """), {"plan_id": free_id})


def downgrade() -> None:
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_plans_active", table_name="plans")
    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
