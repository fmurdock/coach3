"""SQLAlchemy model for Strength Sets."""

from datetime import datetime
import uuid
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class StrengthSet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "strength_sets"
    __table_args__ = (
        CheckConstraint("reps_completed >= 0", name="check_reps_non_negative"),
        CheckConstraint(
            "weight_unit IN ('lbs', 'kg')",
            name="check_weight_unit_valid",
        ),
        CheckConstraint(
            "rpe IS NULL OR (rpe >= 1.0 AND rpe <= 10.0)",
            name="check_rpe_range_valid",
        ),
        Index("idx_strength_set_session", "workout_session_id", "set_index"),
        Index("idx_strength_set_exercise", "exercise_id"),
        Index("idx_strength_set_idempotency", "idempotency_key", unique=True),
    )

    workout_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strength_exercises.id", ondelete="RESTRICT"),
        nullable=False,
    )
    set_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)

    weight: Mapped[float] = mapped_column(Numeric(7, 2), default=0.0, nullable=False)
    weight_unit: Mapped[str] = mapped_column(String(10), default="lbs", nullable=False)

    is_bodyweight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    added_weight: Mapped[float] = mapped_column(Numeric(7, 2), default=0.0, nullable=False)

    rpe: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    is_warmup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    workout_session: Mapped["WorkoutSession"] = relationship(
        "WorkoutSession",
        back_populates="strength_sets",
    )
    exercise: Mapped["StrengthExercise"] = relationship(
        "StrengthExercise",
        back_populates="sets",
    )
