"""Pydantic schemas for integration configuration, diagnostics, and demo data management."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class SaveProviderCredentialsRequest(BaseModel):
    client_id: str | None = Field(
        default=None,
        description="OAuth application Client ID (optional when rotating only client_secret on an existing DB config)",
    )
    client_secret: str = Field(..., min_length=1, description="OAuth application Client Secret")
    redirect_uri: str | None = Field(default=None, description="Optional custom redirect URI")


class ProviderConfigSummary(BaseModel):
    provider: Literal["polar", "concept2"]
    is_configured: bool = Field(..., description="Whether client ID & secret are set and readable")
    is_connected: bool = Field(..., description="Whether an active OAuth account exists")
    masked_client_id: str | None = Field(default=None, description="Partially masked client ID for display")
    source: Literal["database", "env", "none", "decryption_error"] = Field(
        ..., description="Where credentials originated"
    )
    decryption_error: bool = Field(
        default=False,
        description="True when stored credentials cannot be decrypted with current ENCRYPTION_KEY",
    )
    account_id: str | None = Field(default=None, description="External user identifier if connected")
    last_sync_at: datetime | None = Field(default=None, description="Last successful sync time")


class VerificationResult(BaseModel):
    provider: str
    is_connected: bool
    status: Literal["healthy", "expired", "error", "unconfigured"]
    athlete_name: str | None = None
    expires_at: datetime | None = None
    last_sync_at: datetime | None = None
    error_message: str | None = None


class SeedResult(BaseModel):
    status: str = "success"
    workouts_created: int
    strength_sets_created: int
    message: str = "Sample workouts seeded successfully."


class ResetResult(BaseModel):
    status: str = "success"
    workouts_deleted: int
    message: str = "Demo workout records purged successfully."
