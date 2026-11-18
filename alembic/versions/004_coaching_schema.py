"""004_coaching_schema

Revision ID: 004_coaching_schema
Revises: 003_personal_records
Create Date: 2026-11-18 09:10:00.000000

"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_coaching_schema'
down_revision = '003_personal_records'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. llm_provider_configs
    op.create_table(
        'llm_provider_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('endpoint_url', sa.String(255), nullable=False),
        sa.Column('api_key_encrypted', sa.String(500), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('temperature', sa.Numeric(3, 2), server_default='0.7', nullable=False),
        sa.Column('max_tokens', sa.Integer(), server_default='2048', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_llm_provider_user', 'llm_provider_configs', ['user_id'])
    op.create_index('ix_llm_provider_active', 'llm_provider_configs', ['user_id', 'is_active'])

    # 2. coaching_philosophies
    op.create_table(
        'coaching_philosophies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_zone2_pct', sa.Numeric(5, 2), server_default='80.0', nullable=False),
        sa.Column('max_weekly_volume_ramp_pct', sa.Numeric(5, 2), server_default='10.0', nullable=False),
        sa.Column('max_rpe_threshold', sa.Numeric(3, 1), server_default='8.5', nullable=False),
        sa.Column('min_rest_days_per_week', sa.Integer(), server_default='2', nullable=False),
        sa.Column('primary_modality', sa.String(50), server_default='hybrid', nullable=False),
        sa.Column('custom_context_notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_coaching_philosophy_user', 'coaching_philosophies', ['user_id'])
    op.create_index('ix_coaching_philosophy_active', 'coaching_philosophies', ['user_id', 'is_active'])

    # 3. coaching_critiques
    op.create_table(
        'coaching_critiques',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workout_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workout_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('philosophy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('coaching_philosophies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider_used', sa.String(50), nullable=False),
        sa.Column('adherence_score', sa.Numeric(4, 1), nullable=False),
        sa.Column('summary_markdown', sa.Text(), nullable=False),
        sa.Column('adherence_details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('strain_assessment', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('recommendations', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_coaching_critique_user', 'coaching_critiques', ['user_id'])
    op.create_index('ix_coaching_critique_session', 'coaching_critiques', ['workout_session_id'])

    # 4. training_schedule_plans
    op.create_table(
        'training_schedule_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('philosophy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('coaching_philosophies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_goal', sa.String(255), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), server_default='7', nullable=False),
        sa.Column('summary_markdown', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_training_plan_user', 'training_schedule_plans', ['user_id'])
    op.create_index('ix_training_plan_status', 'training_schedule_plans', ['user_id', 'status'])

    # 5. scheduled_workouts
    op.create_table(
        'scheduled_workouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('training_schedule_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('discipline', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('planned_duration_min', sa.Integer(), server_default='45', nullable=False),
        sa.Column('target_distance_m', sa.Numeric(10, 2), nullable=True),
        sa.Column('target_zone', sa.String(50), nullable=True),
        sa.Column('target_rpe', sa.Numeric(3, 1), nullable=True),
        sa.Column('strength_exercises', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scheduled_workout_plan', 'scheduled_workouts', ['plan_id'])
    op.create_index('ix_scheduled_workout_date', 'scheduled_workouts', ['target_date'])


def downgrade() -> None:
    op.drop_table('scheduled_workouts')
    op.drop_table('training_schedule_plans')
    op.drop_table('coaching_critiques')
    op.drop_table('coaching_philosophies')
    op.drop_table('llm_provider_configs')
