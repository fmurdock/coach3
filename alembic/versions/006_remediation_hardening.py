"""006_remediation_hardening

Revision ID: 006_remediation_hardening
Revises: 005_integration_config_and_demo
Create Date: 2026-11-24 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006_remediation_hardening"
down_revision = "005_integration_config_and_demo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # 1. users: timezone + passphrase_hash
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("passphrase_hash", sa.Text(), nullable=True),
    )

    # 2. oauth_states table for single-use expiring OAuth2 CSRF nonces
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(128), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('polar', 'concept2')", name="check_oauth_state_provider_valid"),
    )
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])

    # 3. strength_sets: submission_key + expanded idempotency_key
    op.add_column(
        "strength_sets",
        sa.Column("submission_key", sa.String(100), nullable=True),
    )
    op.create_index(
        "idx_strength_set_submission",
        "strength_sets",
        ["workout_session_id", "submission_key"],
    )

    # 4. PostgreSQL-specific column alterations, constraints & partial unique indexes
    if dialect == "postgresql":
        op.alter_column(
            "strength_sets",
            "idempotency_key",
            existing_type=sa.String(100),
            type_=sa.String(120),
            existing_nullable=True,
        )

        # llm_provider_configs: Text api_key_encrypted + provider check + single-active partial unique index
        op.alter_column(
            "llm_provider_configs",
            "api_key_encrypted",
            existing_type=sa.String(500),
            type_=sa.Text(),
            existing_nullable=True,
        )
        op.create_check_constraint(
            "check_llm_provider_type",
            "llm_provider_configs",
            "provider_type IN ('gemini', 'llama_cpp')",
        )
        op.create_index(
            "uq_llm_provider_active_user",
            "llm_provider_configs",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("is_active IS TRUE"),
        )

        # coaching_philosophies: check constraints + single-active partial unique index
        op.create_check_constraint(
            "check_phil_zone2_pct",
            "coaching_philosophies",
            "target_zone2_pct >= 0 AND target_zone2_pct <= 100",
        )
        op.create_check_constraint(
            "check_phil_rpe",
            "coaching_philosophies",
            "max_rpe_threshold >= 1.0 AND max_rpe_threshold <= 10.0",
        )
        op.create_check_constraint(
            "check_phil_rest_days",
            "coaching_philosophies",
            "min_rest_days_per_week >= 0 AND min_rest_days_per_week <= 7",
        )
        op.create_check_constraint(
            "check_phil_modality",
            "coaching_philosophies",
            "primary_modality IN ('endurance', 'strength', 'hybrid')",
        )
        op.create_index(
            "uq_coaching_philosophy_active_user",
            "coaching_philosophies",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("is_active IS TRUE"),
        )

        # user_heart_rate_profiles: allow resting_hr >= 25 + enforce monotonic zone ordering
        op.drop_constraint("check_hr_bounds", "user_heart_rate_profiles", type_="check")
        op.create_check_constraint(
            "check_hr_bounds",
            "user_heart_rate_profiles",
            "resting_hr >= 25 AND resting_hr < 150 AND max_hr > 120 AND max_hr < 240 AND resting_hr < max_hr",
        )
        op.create_check_constraint(
            "check_hr_zones_ordered",
            "user_heart_rate_profiles",
            "zone1_min > 0 AND zone1_min < zone1_max AND zone1_max <= zone2_min "
            "AND zone2_min < zone2_max AND zone2_max <= zone3_min "
            "AND zone3_min < zone3_max AND zone3_max <= zone4_min "
            "AND zone4_min < zone4_max AND zone4_max <= zone5_min "
            "AND zone5_min < zone5_max",
        )

    # 5. Drop redundant non-unique index on integration_client_configs.provider
    op.drop_index("ix_client_configs_provider", table_name="integration_client_configs")

    # 6. Drop dead unused personal_records table (recreated cleanly in downgrade)
    op.drop_index("ix_personal_records_achieved_at", table_name="personal_records")
    op.drop_index("ix_personal_records_exercise_id", table_name="personal_records")
    op.drop_index("ix_personal_records_discipline", table_name="personal_records")
    op.drop_index("ix_personal_records_user_id", table_name="personal_records")
    op.drop_table("personal_records")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    # Recreate personal_records table
    op.create_table(
        "personal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discipline", sa.String(50), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strength_exercises.id", ondelete="CASCADE"), nullable=True),
        sa.Column("milestone_type", sa.String(50), nullable=False),
        sa.Column("record_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("record_unit", sa.String(20), nullable=False),
        sa.Column("estimated_1rm", sa.Numeric(7, 2), nullable=True),
        sa.Column("workout_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workout_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strength_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strength_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_personal_records_user_id", "personal_records", ["user_id"])
    op.create_index("ix_personal_records_discipline", "personal_records", ["discipline"])
    op.create_index("ix_personal_records_exercise_id", "personal_records", ["exercise_id"])
    op.create_index("ix_personal_records_achieved_at", "personal_records", ["achieved_at"])

    op.create_index("ix_client_configs_provider", "integration_client_configs", ["provider"])

    if dialect == "postgresql":
        op.drop_constraint("check_hr_zones_ordered", "user_heart_rate_profiles", type_="check")
        op.drop_constraint("check_hr_bounds", "user_heart_rate_profiles", type_="check")
        op.create_check_constraint(
            "check_hr_bounds",
            "user_heart_rate_profiles",
            "resting_hr > 30 AND max_hr < 240 AND resting_hr < max_hr",
        )

        op.drop_index("uq_coaching_philosophy_active_user", table_name="coaching_philosophies")
        op.drop_constraint("check_phil_modality", "coaching_philosophies", type_="check")
        op.drop_constraint("check_phil_rest_days", "coaching_philosophies", type_="check")
        op.drop_constraint("check_phil_rpe", "coaching_philosophies", type_="check")
        op.drop_constraint("check_phil_zone2_pct", "coaching_philosophies", type_="check")

        op.drop_index("uq_llm_provider_active_user", table_name="llm_provider_configs")
        op.drop_constraint("check_llm_provider_type", "llm_provider_configs", type_="check")
        op.alter_column(
            "llm_provider_configs",
            "api_key_encrypted",
            existing_type=sa.Text(),
            type_=sa.String(500),
            existing_nullable=True,
        )

        op.alter_column(
            "strength_sets",
            "idempotency_key",
            existing_type=sa.String(120),
            type_=sa.String(100),
            existing_nullable=True,
        )

    op.drop_index("idx_strength_set_submission", table_name="strength_sets")
    op.drop_column("strength_sets", "submission_key")

    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_table("oauth_states")

    op.drop_column("users", "passphrase_hash")
    op.drop_column("users", "timezone")

