"""SQLAlchemy model for Voice Transcription Logs."""

from datetime import datetime
import uuid
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VoiceTranscriptionLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "voice_transcription_logs"
    __table_args__ = (
        Index("idx_voice_log_user", "user_id", "created_at"),
        Index("idx_voice_log_session", "workout_session_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    workout_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    raw_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    was_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    final_confirmed_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="voice_logs",
    )
    workout_session: Mapped["WorkoutSession"] = relationship(
        "WorkoutSession",
        back_populates="voice_logs",
    )
