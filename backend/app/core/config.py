import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "SMART 112 Orchestration Platform"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "smart112"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/smart112"
    )
    
    # Fallback SQLite DB path if PostgreSQL is unavailable
    SQLITE_FALLBACK_URL: str = "sqlite:///./smart112.db"
    
    # Gemini API Key (Zero Cost Free Tier)
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key for emergency NLU")
    
    # Whisper STT configuration
    WHISPER_DEVICE: str = "cuda"
    
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
        "audio/x-wav"
    ]

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
