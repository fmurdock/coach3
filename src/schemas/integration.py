"""Pydantic schemas for external integrations and sync audit logs."""

from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict


class IntegrationAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    account_id: str
    last_sync_at: datetime | None = None
    is_active: bool


class SyncAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    trigger_type: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    items_imported: int
    items_updated: int
    error_message: str | None = None
    diagnostic_metadata: dict[str, Any] | None = None


class AuthUrlResponse(BaseModel):
    auth_url: str


class CodeExchangeRequest(BaseModel):
    code: str
