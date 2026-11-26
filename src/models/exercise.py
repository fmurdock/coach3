"""SQLAlchemy models for Strength Exercises and Aliases."""

from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.strength_set import StrengthSet


class StrengthExercise(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "strength_exercises"
    __table_args__ = (
        CheckConstraint(
            "category IN ('barbell', 'dumbbell', 'bodyweight', 'machine', 'cable')",
            name="check_exercise_category_valid",
        ),
        Index("idx_exercise_slug", "slug", unique=True),
        Index("idx_exercise_category", "category"),
    )

    canonical_name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_muscle_group: Mapped[str] = mapped_column(String(50), nullable=False)
    is_bodyweight: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    default_unit: Mapped[str] = mapped_column(String(10), default="lbs", server_default="lbs", nullable=False)

    # Relationships
    aliases: Mapped[list["ExerciseAlias"]] = relationship(
        "ExerciseAlias",
        back_populates="exercise",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sets: Mapped[list["StrengthSet"]] = relationship(
        "StrengthSet",
        back_populates="exercise",
        lazy="select",
    )


class ExerciseAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "exercise_aliases"
    __table_args__ = (
        Index("idx_exercise_alias", "alias", unique=True),
    )

    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strength_exercises.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String(120), nullable=False)

    # Relationships
    exercise: Mapped["StrengthExercise"] = relationship(
        "StrengthExercise",
        back_populates="aliases",
    )
