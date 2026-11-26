"""Pydantic schemas for single-user authentication endpoints."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    passphrase: str = Field(..., min_length=1, max_length=256)


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_required: bool
    localhost_bypass_active: bool
    passphrase_configured: bool

