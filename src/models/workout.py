"""Canonical WorkoutSession model for all endurance activities."""

from datetime import datetime
import uuid
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkoutSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workout_sessions"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_provider_external_id"),
        CheckConstraint(
            "discipline IN ('outdoor_run', 'indoor_row', 'erg_bike')",
            name="check_discipline_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'archived_upstream')",
            name="check_workout_status_valid",
        ),
        Index("idx_workout_user_date", "user_id", "start_time_utc"),
        Index("idx_workout_discipline", "user_id", "discipline", "start_time_utc"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)

    total_duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    active_duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cardiovascular aggregates
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zone1_duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    zone2_duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    zone3_duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    zone4_duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    zone5_duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Running-specific metrics
    avg_pace_sec_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_loss_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Concept2 erg-specific metrics
    total_strokes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_cadence_spm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_power_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_split_sec_per_500m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_drag_factor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status & Annotations
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workouts")
    heart_rate_samples: Mapped[list["HeartRateSample"]] = relationship(
        "HeartRateSample",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="HeartRateSample.elapsed_sec",
    )
    gps_route_points: Mapped[list["GPSRoutePoint"]] = relationship(
        "GPSRoutePoint",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="GPSRoutePoint.elapsed_sec",
    )
    splits: Mapped[list["WorkoutSplit"]] = relationship(
        "WorkoutSplit",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="WorkoutSplit.split_index",
    )
