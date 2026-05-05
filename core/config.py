"""
Application configuration loaded from environment variables.

Two layers:

- `Settings` (Pydantic BaseSettings): values that may differ per
  environment (DB credentials, API keys, paths). Loaded from .env.
- `Constants`: business invariants that are part of the domain model
  and should be reviewed in code, not configured per environment.
  Things like rate limits, cache TTLs, retry counts, geographic
  bounding boxes.

Both are designed to be injected as dependencies. Avoid importing
`get_settings()` at module level outside of the composition root —
that creates hidden coupling that makes testing harder.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    # ── JWT Auth ─────────────────────────────────────────────────────
    # NOTE: in Phase 3 we plan to reduce the access-token lifetime to
    # 60 minutes (refresh handled by re-issuing via Telegram initData).
    # The current 7-day default is preserved for backwards
    # compatibility until the auth feature is migrated.
    JWT_SECRET: str = "changeme_in_production_jwt_secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # ── Telegram & AI ────────────────────────────────────────────────
    BOT_TOKEN: str
    KIMI_CODE_API_KEY: str
    DEEPSEEK_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    MAPBOX_TOKEN: str = ""

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]

    # ── Media ────────────────────────────────────────────────────────
    MEDIA_DIR: str = "/home/ubuntu/Phangan/TG_parcer/media"
    SHARE_CARD_DIR: str = "/home/ubuntu/Phangan/TG_parcer/media/share"
    AVATARS_DIR: str = "avatars"
    PUBLIC_API_BASE_URL: str = "https://api.fastpump.fun"
    PUBLIC_MEDIA_BASE_URL: str = "https://api.fastpump.fun/api/media"
    PUBLIC_SHARE_BASE_URL: str = "https://api.fastpump.fun/api/media/share"
    PUBLIC_MINIAPP_URL: str = "https://phangan.fastpump.fun/"
    TELEGRAM_BOT_USERNAME: str = "GoPhanganBot"

    # ── Observability ────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" | "text"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@dataclass(frozen=True)
class Constants:
    """
    Domain-level invariants and tunables.

    These are intentionally hard-coded (not env-overridable) because
    changing them is a code-review-worthy decision, not a deployment
    parameter. If a value here genuinely needs to vary per environment,
    promote it to `Settings`.
    """

    # ── Geography (Koh Phangan bounding box) ─────────────────────────
    PHANGAN_BBOX_LAT_MIN: float = 9.65
    PHANGAN_BBOX_LAT_MAX: float = 9.84
    PHANGAN_BBOX_LNG_MIN: float = 99.91
    PHANGAN_BBOX_LNG_MAX: float = 100.14

    # ── Distance / travel ────────────────────────────────────────────
    HAVERSINE_ROAD_FACTOR: float = 1.4
    SCOOTER_KMH: int = 25
    DISTANCE_CACHE_TTL_S: int = 86_400  # 24 hours
    DISTANCE_GRID_PRECISION: int = 3
    MAPBOX_BATCH_SIZE: int = 24

    # ── Facepile ─────────────────────────────────────────────────────
    FACEPILE_CACHE_TTL_S: int = 60
    FACEPILE_MIN_REAL_AVATARS: int = 5
    FACEPILE_PHANTOM_OPPOSITE_GENDER_RATIO: float = 0.65

    # ── Onboarding ──────────────────────────────────────────────────
    USER_MOOD_CONTEXT_TTL_HOURS: int = 6

    # ── Cache defaults ───────────────────────────────────────────────
    CACHE_DEFAULT_TTL_S: int = 300
    CACHE_DEFAULT_MAX_ENTRIES: int = 5_000


@lru_cache
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Cached after first call to avoid repeated .env parsing. Use this
    only at the composition root — pass `Settings` explicitly to
    services and use cases instead of calling `get_settings()` deep in
    business logic.
    """
    return Settings()  # type: ignore[call-arg]


@lru_cache
def get_constants() -> Constants:
    """Return the singleton Constants instance."""
    return Constants()
