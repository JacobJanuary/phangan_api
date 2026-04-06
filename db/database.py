"""
Database connection pool management.

Uses asyncpg for high-performance async PostgreSQL access.
Pool lifecycle is tied to the FastAPI application lifespan.
"""

from __future__ import annotations

import logging

import asyncpg

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Module-level pool reference, managed by lifespan
_pool: asyncpg.Pool | None = None


async def create_pool(settings: Settings | None = None) -> asyncpg.Pool:
    """Create and return a new asyncpg connection pool."""
    global _pool  # noqa: PLW0603
    if settings is None:
        settings = get_settings()

    _pool = await asyncpg.create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        min_size=settings.DB_MIN_POOL,
        max_size=settings.DB_MAX_POOL,
    )
    logger.info(
        "✅ Database pool created: %s:%d/%s (pool: %d–%d)",
        settings.DB_HOST,
        settings.DB_PORT,
        settings.DB_NAME,
        settings.DB_MIN_POOL,
        settings.DB_MAX_POOL,
    )
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        logger.info("🔌 Database pool closed.")
        _pool = None


def get_pool() -> asyncpg.Pool:
    """
    FastAPI dependency — returns the active connection pool.

    Raises RuntimeError if the pool hasn't been created (lifespan issue).
    """
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Check application lifespan.")
    return _pool
