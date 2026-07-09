"""Application configuration via environment variables."""
from __future__ import annotations

import os
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
    DATABASE_URL: str = "sqlite+aiosqlite:///./woven_licensing.db"

    # JWT
    JWT_SECRET_KEY: str = "change-me-jwt"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Admin account
    ADMIN_EMAIL: str = "admin@wovenmodel.com"
    ADMIN_PASSWORD: Optional[str] = None

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
        url = self.DATABASE_URL
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def admin_password_resolved(self) -> Optional[str]:
        """Resolve admin password from env with fallback.

        pydantic-settings may not pick up Railway env vars in some cases,
        so we fall back to os.environ directly.
        """
        if self.ADMIN_PASSWORD:
            return self.ADMIN_PASSWORD
        # Direct fallback — bypass pydantic
        env_val = os.environ.get("ADMIN_PASSWORD")
        if env_val:
            return env_val
        env_val = os.environ.get("admin_password")
        if env_val:
            return env_val
        return None


settings = Settings()
