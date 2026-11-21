"""005_integration_config_and_demo

Revision ID: 005_integration_config_and_demo
Revises: 004_coaching_schema
Create Date: 2026-11-18 20:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_integration_config_and_demo"
down_revision = "004_coaching_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create integration_client_configs table
    op.create_table(
        "integration_client_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_client_id", sa.Text(), nullable=False),
        sa.Column("encrypted_client_secret", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('polar', 'concept2')", name="check_client_provider_valid"),
        sa.UniqueConstraint("provider", name="uq_client_config_provider"),
    )
    op.create_index("ix_client_configs_provider", "integration_client_configs", ["provider"])

    # 2. Add is_demo column to workout_sessions
    op.add_column(
        "workout_sessions",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_workout_sessions_is_demo", "workout_sessions", ["is_demo"])


def downgrade() -> None:
    op.drop_index("ix_workout_sessions_is_demo", table_name="workout_sessions")
    op.drop_column("workout_sessions", "is_demo")
    op.drop_index("ix_client_configs_provider", table_name="integration_client_configs")
    op.drop_table("integration_client_configs")
