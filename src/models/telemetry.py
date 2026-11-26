"""Telemetry streams: Heart rate samples, GPS route points, and interval splits."""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.workout import WorkoutSession


class HeartRateSample(Base):
    __tablename__ = "heart_rate_samples"
    __table_args__ = (
        Index("idx_hr_workout_elapsed", "workout_id", "elapsed_sec"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    workout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    elapsed_sec: Mapped[float] = mapped_column(Float, nullable=False)
    bpm: Mapped[int] = mapped_column(Integer, nullable=False)

    workout: Mapped["WorkoutSession"] = relationship("WorkoutSession", back_populates="heart_rate_samples")


class GPSRoutePoint(Base):
    __tablename__ = "gps_route_points"
    __table_args__ = (
        Index("idx_gps_workout_elapsed", "workout_id", "elapsed_sec"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    workout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    elapsed_sec: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(DOUBLE_PRECISION().with_variant(Float, "sqlite"), nullable=False)
    longitude: Mapped[float] = mapped_column(DOUBLE_PRECISION().with_variant(Float, "sqlite"), nullable=False)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    workout: Mapped["WorkoutSession"] = relationship("WorkoutSession", back_populates="gps_route_points")


class WorkoutSplit(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "workout_splits"
    __table_args__ = (
        Index("idx_split_workout_order", "workout_id", "split_index"),
    )

    workout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    split_index: Mapped[int] = mapped_column(Integer, nullable=False)
    split_type: Mapped[str] = mapped_column(String(50), default="interval", nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    avg_pace_sec_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_power_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cadence_spm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_split_sec_per_500m: Mapped[float | None] = mapped_column(Float, nullable=True)

    workout: Mapped["WorkoutSession"] = relationship("WorkoutSession", back_populates="splits")
