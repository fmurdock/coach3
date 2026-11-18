"""SQLAlchemy model for Personal Records (PRs)."""

from datetime import datetime
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class PersonalRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "personal_records"
    __table_args__ = (
        Index("ix_personal_records_user_id", "user_id"),
        Index("ix_personal_records_discipline", "discipline"),
        Index("ix_personal_records_exercise_id", "exercise_id"),
        Index("ix_personal_records_achieved_at", "achieved_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    discipline: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'strength', 'outdoor_run', 'indoor_row', 'erg_bike'
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strength_exercises.id", ondelete="CASCADE"),
        nullable=True,
    )
    milestone_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'weight_pr', 'estimated_1rm_pr', 'repetition_pr', '1_mile', '5k', '10k', '500m_erg', '2k_erg', '5k_erg'
    record_value: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    record_unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 'lbs', 'kg', 'sec', 'sec_per_km', 'sec_per_500m', 'reps'
    estimated_1rm: Mapped[float | None] = mapped_column(
        Numeric(7, 2),
        nullable=True,
    )
    workout_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    strength_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strength_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    user = relationship("User")
    exercise = relationship("StrengthExercise")
    workout_session = relationship("WorkoutSession")
    strength_set = relationship("StrengthSet")
