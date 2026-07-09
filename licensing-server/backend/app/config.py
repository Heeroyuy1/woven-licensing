"""Application configuration via environment variables."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "Woven Model Licensing Server"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"
    ENVIRONMENT: str = "production"

    # Database
    # NOTE: Railway PostgreSQL add-on sets DATABASE_URL=postgresql://user:pass@host/db
    # Config auto-translates postgresql:// → postgresql+asyncpg:// for async driver.
    DATABASE_URL: str = "sqlite+aiosqlite:///./woven_licensing.db"

    # JWT
    JWT_SECRET_KEY: str = "change-me-jwt"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Admin account (used for seeding on startup)
    ADMIN_EMAIL: str = "admin@wovenmodel.com"
    ADMIN_PASSWORD: Optional[str] = None  # if None, a random password is generated

    # Signing Keys (Ed25519 hex-encoded)
    SIGNING_PRIVATE_KEY: Optional[str] = None
    SIGNING_PUBLIC_KEY: Optional[str] = None

    # SMTP
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@wovenmodel.com"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Database Pool
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        """Return the DATABASE_URL with the correct async driver prefix.

        Railway PostgreSQL add-on sets DATABASE_URL=postgresql://user:pass@host/db
        but SQLAlchemy async engine requires postgresql+asyncpg:// instead.
        SQLite stays as-is since aiosqlite is the default.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
