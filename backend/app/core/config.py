import os
from typing import List, Optional
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SMART 112"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # PostgreSQL / PostGIS configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "smart112"
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20
    POSTGRES_CONNECT_TIMEOUT: int = 5

    # Project-scoped DSN override. Takes precedence over the generic DATABASE_URL so
    # an unrelated machine-wide DATABASE_URL (common on shared dev machines) cannot
    # redirect SMART 112 migrations/tests into an arbitrary local PostgreSQL database.
    SMART112_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Explicit DSN override for SMART 112. Highest priority.",
    )

    # Standard database URL (used by Docker Compose, Render, Heroku, etc.)
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Full SQLAlchemy DSN. Defaults to postgresql://<user>:<pass>@<host>:<port>/<db>.",
    )

    # Fallback SQLite DB path if PostgreSQL is unavailable
    SQLITE_FALLBACK_URL: str = "sqlite:///./smart112.db"

    # Gemini API Key (Zero Cost Free Tier)
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key for emergency NLU")

    # Whisper STT configuration
    WHISPER_DEVICE: str = "cuda"
    SIMULATE_STT_FOR_TESTS: bool = True

    # Dispatcher security credentials & tokens
    DISPATCHER_AUTH_TOKEN: str = "smart112-dispatch-key-2026"

    # CORS Origins (comma-separated or list)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    # Urban dispatch default speed (km/h) for ETA calculation
    URBAN_SPEED_KMH: float = 40.0

    # Default regional center (Guntur / Vijayawada)
    DEFAULT_LATITUDE: float = 16.3067
    DEFAULT_LONGITUDE: float = 80.4365

    # File upload limits
    MAX_AUDIO_UPLOAD_BYTES: int = 15 * 1024 * 1024  # 15 MB
    ALLOWED_AUDIO_MIME_TYPES: List[str] = [
        "audio/wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/x-wav",
    ]

    # Destructive operator utilities (purge-all) are refused in production.
    ENABLE_DESTRUCTIVE_ENDPOINTS: bool = True

    # Test/CI switch: skip schema creation + seeding on application startup. The
    # test suite owns its own in-memory schema and must never mutate a live database.
    SKIP_STARTUP_HOOKS: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    def _coerce_cors_origins(cls, value):
        if isinstance(value, (list, tuple, set)):
            return ",".join(str(item) for item in value)
        return value

    @model_validator(mode="after")
    def _normalize_database_url(self):
        url = (self.SMART112_DATABASE_URL or self.DATABASE_URL or "").strip()

        # Heroku/Render style shorthand uses the legacy `postgres://` scheme which
        # SQLAlchemy 2.x no longer recognizes. SQLAlchemy 2.1+ also defaults bare
        # postgresql:// to the psycopg (v3) driver, so we normalize to explicit
        # postgresql+psycopg2:// unless a specific DBAPI driver is already declared.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://") :]

        if not url:
            url = (
                f"postgresql+psycopg2://{quote_plus(self.POSTGRES_USER)}:"
                f"{quote_plus(self.POSTGRES_PASSWORD)}@"
                f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        self.DATABASE_URL = url
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"prod", "production"}


settings = Settings()
