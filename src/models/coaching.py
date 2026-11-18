"""SQLAlchemy models for Adaptive AI Coaching, Philosophies, and Plans."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class LLMProviderConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "llm_provider_configs"
    __table_args__ = (
        Index("ix_llm_provider_user", "user_id"),
        Index("ix_llm_provider_active", "user_id", "is_active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'gemini' or 'llama_cpp'
    endpoint_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    temperature: Mapped[float] = mapped_column(
        Numeric(3, 2),
        default=0.7,
        nullable=False,
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=2048,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    user = relationship("User")


class CoachingPhilosophy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coaching_philosophies"
    __table_args__ = (
        Index("ix_coaching_philosophy_user", "user_id"),
        Index("ix_coaching_philosophy_active", "user_id", "is_active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    target_zone2_pct: Mapped[float] = mapped_column(
        Numeric(5, 2),
        default=80.0,
        nullable=False,
    )
    max_weekly_volume_ramp_pct: Mapped[float] = mapped_column(
        Numeric(5, 2),
        default=10.0,
        nullable=False,
    )
    max_rpe_threshold: Mapped[float] = mapped_column(
        Numeric(3, 1),
        default=8.5,
        nullable=False,
    )
    min_rest_days_per_week: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )
    primary_modality: Mapped[str] = mapped_column(
        String(50),
        default="hybrid",
        nullable=False,
    )  # 'endurance', 'strength', 'hybrid'
    custom_context_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    user = relationship("User")


class CoachingCritique(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coaching_critiques"
    __table_args__ = (
        Index("ix_coaching_critique_user", "user_id"),
        Index("ix_coaching_critique_session", "workout_session_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    workout_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    philosophy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coaching_philosophies.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_used: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'gemini' or 'llama_cpp'
    adherence_score: Mapped[float] = mapped_column(
        Numeric(4, 1),
        nullable=False,
    )
    summary_markdown: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    adherence_details: Mapped[Dict[str, Any]] = mapped_column(
        JSON_TYPE,
        default=dict,
        nullable=False,
    )
    strain_assessment: Mapped[Dict[str, Any]] = mapped_column(
        JSON_TYPE,
        default=dict,
        nullable=False,
    )
    recommendations: Mapped[List[Any]] = mapped_column(
        JSON_TYPE,
        default=list,
        nullable=False,
    )

    user = relationship("User")
    workout_session = relationship("WorkoutSession")
    philosophy = relationship("CoachingPhilosophy")


class TrainingSchedulePlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_schedule_plans"
    __table_args__ = (
        Index("ix_training_plan_user", "user_id"),
        Index("ix_training_plan_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    philosophy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coaching_philosophies.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_goal: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    horizon_days: Mapped[int] = mapped_column(
        Integer,
        default=7,
        nullable=False,
    )
    summary_markdown: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
    )  # 'active', 'completed', 'superseded'

    user = relationship("User")
    philosophy = relationship("CoachingPhilosophy")
    scheduled_workouts = relationship(
        "ScheduledWorkout",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ScheduledWorkout.target_date.asc()",
    )


class ScheduledWorkout(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scheduled_workouts"
    __table_args__ = (
        Index("ix_scheduled_workout_plan", "plan_id"),
        Index("ix_scheduled_workout_date", "target_date"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_schedule_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    discipline: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'outdoor_run', 'indoor_row', 'erg_bike', 'strength', 'rest'
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    planned_duration_min: Mapped[int] = mapped_column(
        Integer,
        default=45,
        nullable=False,
    )
    target_distance_m: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    target_zone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    target_rpe: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 1),
        nullable=True,
    )
    strength_exercises: Mapped[Optional[List[Any]]] = mapped_column(
        JSON_TYPE,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    plan = relationship("TrainingSchedulePlan", back_populates="scheduled_workouts")
