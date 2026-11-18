"""User and Heart Rate Profile models."""

import uuid
from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # Relationships
    hr_profile: Mapped["UserHeartRateProfile"] = relationship(
        "UserHeartRateProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    integration_accounts: Mapped[list["IntegrationAccount"]] = relationship(
        "IntegrationAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    workouts: Mapped[list["WorkoutSession"]] = relationship(
        "WorkoutSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserHeartRateProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_heart_rate_profiles"
    __table_args__ = (
        CheckConstraint(
            "resting_hr > 30 AND max_hr < 240 AND resting_hr < max_hr",
            name="check_hr_bounds",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    resting_hr: Mapped[int] = mapped_column(Integer, nullable=False)
    max_hr: Mapped[int] = mapped_column(Integer, nullable=False)

    zone1_min: Mapped[int] = mapped_column(Integer, nullable=False)
    zone1_max: Mapped[int] = mapped_column(Integer, nullable=False)
    zone2_min: Mapped[int] = mapped_column(Integer, nullable=False)
    zone2_max: Mapped[int] = mapped_column(Integer, nullable=False)
    zone3_min: Mapped[int] = mapped_column(Integer, nullable=False)
    zone3_max: Mapped[int] = mapped_column(Integer, nullable=False)
    zone4_min: Mapped[int] = mapped_column(Integer, nullable=False)
    zone4_max: Mapped[int] = mapped_column(Integer, nullable=False)
    zone5_min: Mapped[int] = mapped_column(Integer, nullable=False)
    zone5_max: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="hr_profile")
