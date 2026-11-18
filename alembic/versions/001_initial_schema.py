"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-17 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # User Heart Rate Profile
    op.create_table(
        'user_heart_rate_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('resting_hr', sa.Integer(), nullable=False),
        sa.Column('max_hr', sa.Integer(), nullable=False),
        sa.Column('zone1_min', sa.Integer(), nullable=False),
        sa.Column('zone1_max', sa.Integer(), nullable=False),
        sa.Column('zone2_min', sa.Integer(), nullable=False),
        sa.Column('zone2_max', sa.Integer(), nullable=False),
        sa.Column('zone3_min', sa.Integer(), nullable=False),
        sa.Column('zone3_max', sa.Integer(), nullable=False),
        sa.Column('zone4_min', sa.Integer(), nullable=False),
        sa.Column('zone4_max', sa.Integer(), nullable=False),
        sa.Column('zone5_min', sa.Integer(), nullable=False),
        sa.Column('zone5_max', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('resting_hr > 30 AND max_hr < 240 AND resting_hr < max_hr', name='check_hr_bounds'),
    )

    # Integration Accounts
    op.create_table(
        'integration_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('account_id', sa.String(100), nullable=False),
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_cursor', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('polar', 'concept2')", name='check_provider_valid'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
    )

    # Sync Audit Logs
    op.create_table(
        'sync_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('items_imported', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('diagnostic_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('running', 'success', 'partial', 'failed')", name='check_audit_status_valid'),
        sa.CheckConstraint("trigger_type IN ('hourly_schedule', 'manual', 'initial_backfill')", name='check_trigger_type_valid'),
    )

    # Workout Sessions
    op.create_table(
        'workout_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(200), nullable=False),
        sa.Column('discipline', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('start_time_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('local_timezone', sa.String(50), nullable=False, server_default='UTC'),
        sa.Column('total_duration_sec', sa.Float(), nullable=False),
        sa.Column('active_duration_sec', sa.Float(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total_calories', sa.Integer(), nullable=True),
        sa.Column('avg_heart_rate', sa.Integer(), nullable=True),
        sa.Column('max_heart_rate', sa.Integer(), nullable=True),
        sa.Column('zone1_duration_sec', sa.Float(), nullable=False, server_default='0'),
        sa.Column('zone2_duration_sec', sa.Float(), nullable=False, server_default='0'),
        sa.Column('zone3_duration_sec', sa.Float(), nullable=False, server_default='0'),
        sa.Column('zone4_duration_sec', sa.Float(), nullable=False, server_default='0'),
        sa.Column('zone5_duration_sec', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_pace_sec_per_km', sa.Float(), nullable=True),
        sa.Column('elevation_gain_m', sa.Float(), nullable=True),
        sa.Column('elevation_loss_m', sa.Float(), nullable=True),
        sa.Column('total_strokes', sa.Integer(), nullable=True),
        sa.Column('avg_cadence_spm', sa.Float(), nullable=True),
        sa.Column('avg_power_watts', sa.Float(), nullable=True),
        sa.Column('avg_split_sec_per_500m', sa.Float(), nullable=True),
        sa.Column('avg_drag_factor', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('raw_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('provider', 'external_id', name='uq_provider_external_id'),
        sa.CheckConstraint("discipline IN ('outdoor_run', 'indoor_row', 'erg_bike')", name='check_discipline_valid'),
        sa.CheckConstraint("status IN ('active', 'archived_upstream')", name='check_workout_status_valid'),
    )
    op.create_index('idx_workout_user_date', 'workout_sessions', ['user_id', 'start_time_utc'])
    op.create_index('idx_workout_discipline', 'workout_sessions', ['user_id', 'discipline', 'start_time_utc'])

    # Heart Rate Samples
    op.create_table(
        'heart_rate_samples',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('workout_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workout_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('elapsed_sec', sa.Float(), nullable=False),
        sa.Column('bpm', sa.Integer(), nullable=False),
    )
    op.create_index('idx_hr_workout_elapsed', 'heart_rate_samples', ['workout_id', 'elapsed_sec'])

    # GPS Route Points
    op.create_table(
        'gps_route_points',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('workout_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workout_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('elapsed_sec', sa.Float(), nullable=False),
        sa.Column('latitude', postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column('longitude', postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column('altitude_m', sa.Float(), nullable=True),
    )
    op.create_index('idx_gps_workout_elapsed', 'gps_route_points', ['workout_id', 'elapsed_sec'])

    # Workout Splits
    op.create_table(
        'workout_splits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workout_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workout_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('split_index', sa.Integer(), nullable=False),
        sa.Column('split_type', sa.String(50), nullable=False, server_default='interval'),
        sa.Column('distance_m', sa.Float(), nullable=False),
        sa.Column('duration_sec', sa.Float(), nullable=False),
        sa.Column('avg_pace_sec_per_km', sa.Float(), nullable=True),
        sa.Column('avg_power_watts', sa.Float(), nullable=True),
        sa.Column('avg_cadence_spm', sa.Float(), nullable=True),
        sa.Column('avg_heart_rate', sa.Integer(), nullable=True),
        sa.Column('avg_split_sec_per_500m', sa.Float(), nullable=True),
    )
    op.create_index('idx_split_workout_order', 'workout_splits', ['workout_id', 'split_index'])


def downgrade() -> None:
    op.drop_table('workout_splits')
    op.drop_table('gps_route_points')
    op.drop_table('heart_rate_samples')
    op.drop_table('workout_sessions')
    op.drop_table('sync_audit_logs')
    op.drop_table('integration_accounts')
    op.drop_table('user_heart_rate_profiles')
    op.drop_table('users')
