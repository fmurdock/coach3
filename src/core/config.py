"""Application configuration and settings using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development")
    PORT: int = Field(default=8000)

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://coach:coach_secret@localhost:5432/coach3_dev"
    )

    # Cryptography
    # 32 url-safe base64-encoded bytes for Fernet
    ENCRYPTION_KEY: str = Field(
        default="AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
    )

    # Polar AccessLink Integration
    POLAR_CLIENT_ID: str = Field(default="")
    POLAR_CLIENT_SECRET: str = Field(default="")
    POLAR_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/v1/integrations/polar/callback"
    )

    # Concept2 Logbook Integration
    CONCEPT2_CLIENT_ID: str = Field(default="")
    CONCEPT2_CLIENT_SECRET: str = Field(default="")
    CONCEPT2_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/v1/integrations/concept2/callback"
    )

    # Scheduling
    SYNC_INTERVAL_MINUTES: int = Field(default=60)


settings = Settings()
