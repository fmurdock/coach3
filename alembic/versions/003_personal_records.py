"""003_personal_records

Revision ID: 003_personal_records
Revises: 002_gym_mode_schema
Create Date: 2026-11-17 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_personal_records'
down_revision = '002_gym_mode_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'personal_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('discipline', sa.String(50), nullable=False),
        sa.Column('exercise_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strength_exercises.id', ondelete='CASCADE'), nullable=True),
        sa.Column('milestone_type', sa.String(50), nullable=False),
        sa.Column('record_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('record_unit', sa.String(20), nullable=False),
        sa.Column('estimated_1rm', sa.Numeric(7, 2), nullable=True),
        sa.Column('workout_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workout_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('strength_set_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strength_sets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('achieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_personal_records_user_id', 'personal_records', ['user_id'])
    op.create_index('ix_personal_records_discipline', 'personal_records', ['discipline'])
    op.create_index('ix_personal_records_exercise_id', 'personal_records', ['exercise_id'])
    op.create_index('ix_personal_records_achieved_at', 'personal_records', ['achieved_at'])


def downgrade() -> None:
    op.drop_index('ix_personal_records_achieved_at', table_name='personal_records')
    op.drop_index('ix_personal_records_exercise_id', table_name='personal_records')
    op.drop_index('ix_personal_records_discipline', table_name='personal_records')
    op.drop_index('ix_personal_records_user_id', table_name='personal_records')
    op.drop_table('personal_records')
