"""Integration Account, Client Config, OAuth State, and Sync Audit Log models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, JSON_TYPE, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from src.models.user import User


class IntegrationClientConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores encrypted OAuth developer credentials (client ID & secret) per provider."""
    __tablename__ = "integration_client_configs"
    __table_args__ = (
        CheckConstraint("provider IN ('polar', 'concept2')", name="check_client_provider_valid"),
        UniqueConstraint("provider", name="uq_client_config_provider"),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_client_id: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_client_secret: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)


class OAuthState(Base):
    """Stores single-use, expiring OAuth2 CSRF state nonces."""
    __tablename__ = "oauth_states"
    __table_args__ = (
        CheckConstraint("provider IN ('polar', 'concept2')", name="check_oauth_state_provider_valid"),
        Index("ix_oauth_states_expires_at", "expires_at"),
    )

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class IntegrationAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "integration_accounts"
    __table_args__ = (
        CheckConstraint("provider IN ('polar', 'concept2')", name="check_provider_valid"),
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="integration_accounts")


class SyncAuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sync_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')",
            name="check_audit_status_valid",
        ),
        CheckConstraint(
            "trigger_type IN ('hourly_schedule', 'manual', 'initial_backfill')",
            name="check_trigger_type_valid",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    items_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
