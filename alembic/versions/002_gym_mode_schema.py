"""002_gym_mode_schema

Revision ID: 002_gym_mode_schema
Revises: 001_initial_schema
Create Date: 2026-11-17 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_gym_mode_schema'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update workout_sessions check constraint to include 'strength'
    # In PostgreSQL, we can drop and re-add the constraint
    try:
        op.drop_constraint('check_discipline_valid', 'workout_sessions', type_='check')
        op.create_check_constraint(
            'check_discipline_valid',
            'workout_sessions',
            "discipline IN ('outdoor_run', 'indoor_row', 'erg_bike', 'strength')",
        )
    except Exception:
        pass  # In SQLite test environments, alter table check constraint may not be supported

    # 1. strength_exercises
    op.create_table(
        'strength_exercises',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('canonical_name', sa.String(120), nullable=False),
        sa.Column('slug', sa.String(120), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('primary_muscle_group', sa.String(50), nullable=False),
        sa.Column('is_bodyweight', sa.Boolean(), default=False, nullable=False),
        sa.Column('default_unit', sa.String(10), default='lbs', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('barbell', 'dumbbell', 'bodyweight', 'machine', 'cable')",
            name='check_exercise_category_valid',
        ),
    )
    op.create_index('idx_exercise_slug', 'strength_exercises', ['slug'], unique=True)
    op.create_index('idx_exercise_category', 'strength_exercises', ['category'])

    # 2. exercise_aliases
    op.create_table(
        'exercise_aliases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'exercise_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('strength_exercises.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('alias', sa.String(120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_exercise_alias', 'exercise_aliases', ['alias'], unique=True)

    # 3. strength_sets
    op.create_table(
        'strength_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'workout_session_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('workout_sessions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'exercise_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('strength_exercises.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('set_index', sa.Integer(), nullable=False),
        sa.Column('reps_completed', sa.Integer(), nullable=False),
        sa.Column('target_reps', sa.Integer(), nullable=True),
        sa.Column('weight', sa.Numeric(7, 2), default=0.0, nullable=False),
        sa.Column('weight_unit', sa.String(10), default='lbs', nullable=False),
        sa.Column('is_bodyweight', sa.Boolean(), default=False, nullable=False),
        sa.Column('added_weight', sa.Numeric(7, 2), default=0.0, nullable=False),
        sa.Column('rpe', sa.Numeric(3, 1), nullable=True),
        sa.Column('is_warmup', sa.Boolean(), default=False, nullable=False),
        sa.Column('rest_seconds', sa.Integer(), nullable=True),
        sa.Column('idempotency_key', sa.String(100), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('reps_completed >= 0', name='check_reps_non_negative'),
        sa.CheckConstraint("weight_unit IN ('lbs', 'kg')", name='check_weight_unit_valid'),
        sa.CheckConstraint(
            'rpe IS NULL OR (rpe >= 1.0 AND rpe <= 10.0)',
            name='check_rpe_range_valid',
        ),
    )
    op.create_index('idx_strength_set_session', 'strength_sets', ['workout_session_id', 'set_index'])
    op.create_index('idx_strength_set_exercise', 'strength_sets', ['exercise_id'])
    op.create_index('idx_strength_set_idempotency', 'strength_sets', ['idempotency_key'], unique=True)

    # 4. voice_transcription_logs
    op.create_table(
        'voice_transcription_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'workout_session_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('workout_sessions.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('raw_transcript', sa.Text(), nullable=False),
        sa.Column('parsed_json', postgresql.JSONB(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('was_edited', sa.Boolean(), default=False, nullable=False),
        sa.Column('final_confirmed_json', postgresql.JSONB(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_voice_log_user', 'voice_transcription_logs', ['user_id', 'created_at'])
    op.create_index('idx_voice_log_session', 'voice_transcription_logs', ['workout_session_id'])


def downgrade() -> None:
    op.drop_table('voice_transcription_logs')
    op.drop_table('strength_sets')
    op.drop_table('exercise_aliases')
    op.drop_table('strength_exercises')
