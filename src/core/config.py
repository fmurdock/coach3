"""Application configuration and settings using Pydantic Settings."""

from cryptography.fernet import Fernet
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_EXAMPLE_ENCRYPTION_KEY = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="


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
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=30000, ge=1000, le=300000)

    # Cryptography (REQUIRED in non-test environments; no hardcoded default)
    ENCRYPTION_KEY: str = Field(default="")

    # Single-User Passphrase Authentication
    COACH3_PASSPHRASE: str = Field(default="")
    COACH3_PASSPHRASE_HASH: str = Field(default="")
    AUTH_DISABLED_LOCALHOST: bool = Field(default=True)
    SESSION_TTL_DAYS: int = Field(default=30, ge=1, le=365)

    # Web Security, Reverse Proxy & Privacy Scrubbing
    ALLOWED_ORIGINS: str = Field(default="http://localhost:8000,http://127.0.0.1:8000")
    TRUST_PROXY_HEADERS: bool = Field(default=False)
    ALLOWED_LLM_HOSTS: str = Field(default="")
    SCRUB_TERMS: str = Field(default="")

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

    # Scheduling & Sync Limits
    SYNC_INTERVAL_MINUTES: int = Field(default=60, ge=5, le=1440)
    SYNC_PAGE_LIMIT: int = Field(default=50, ge=1, le=500)

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parsed list of trusted browser origins (never wildcard)."""
        origins = [o.strip().rstrip("/") for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return [o for o in origins if o != "*"]

    @property
    def allowed_llm_hosts_list(self) -> list[str]:
        return [h.strip().lower() for h in self.ALLOWED_LLM_HOSTS.split(",") if h.strip()]

    @property
    def scrub_terms_list(self) -> list[str]:
        return [t.strip() for t in self.SCRUB_TERMS.split(",") if t.strip()]

    @model_validator(mode="after")
    def _validate_security_settings(self) -> "Settings":
        env = self.ENVIRONMENT.lower().strip()
        if not self.ENCRYPTION_KEY:
            if env == "test":
                self.ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")
            else:
                raise ValueError(
                    "ENCRYPTION_KEY is required and must be a valid 32-byte url-safe base64 Fernet key. "
                    "Generate one with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
        if env != "test" and self.ENCRYPTION_KEY.strip() == INSECURE_EXAMPLE_ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY cannot use the insecure example placeholder key. "
                "Generate a unique Fernet key for this deployment."
            )
        try:
            Fernet(self.ENCRYPTION_KEY.encode("utf-8"))
        except Exception as exc:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {exc}") from exc
        return self


settings = Settings()
