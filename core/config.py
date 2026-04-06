"""
Core application configuration.

Loads all settings from environment variables (.env file).
Uses Pydantic BaseSettings for validation and type coercion.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # ── Database ─────────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "ThaiApp"
    DB_USER: str
    DB_PASSWORD: str
    DB_MIN_POOL: int = 2
    DB_MAX_POOL: int = 10

    # ── Security ─────────────────────────────────────────────────────
    IP_STRIKE_LIMIT: int = 3
    
    # ── JWT Auth ──────────────────────────────────────────────────────
    JWT_SECRET: str = "changeme_in_production_jwt_secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080 # 7 days

    # ── Telegram & AI ────────────────────────────────────────────────
    BOT_TOKEN: str
    GEMINI_API_KEY: str
    MAPBOX_TOKEN: str = ""

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]

    # ── Phantom ──────────────────────────────────────────────────────

    # ── Media ────────────────────────────────────────────────────────
    MEDIA_DIR: str = "/home/ubuntu/Phangan/TG_parcer/media"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance. Cached after first call."""
    return Settings()
