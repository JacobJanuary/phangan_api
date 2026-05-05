"""
asyncpg connection pool lifecycle.

The pool is the single piece of mutable infrastructure state shared
across requests. It lives at module scope intentionally — every other
component receives it via dependency injection.

Lifecycle is managed by the FastAPI app's `lifespan` context manager,
which calls `create_pool()` on startup and `close_pool()` on shutdown.
"""

from __future__ import annotations

import logging

import asyncpg

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def create_pool(settings: Settings | None = None) -> asyncpg.Pool:
    """
    Create the global asyncpg connection pool.

    Idempotent only in the sense that callers shouldn't invoke it
    twice — doing so leaks the previous pool. The lifespan handler
    is the single legitimate caller.
    """
    global _pool  # noqa: PLW0603

    settings = settings or get_settings()

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
        "database pool ready",
        extra={
            "db_host": settings.DB_HOST,
            "db_port": settings.DB_PORT,
            "db_name": settings.DB_NAME,
            "pool_min": settings.DB_MIN_POOL,
            "pool_max": settings.DB_MAX_POOL,
        },
    )
    return _pool


async def close_pool() -> None:
    """Gracefully release all pool connections."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        return
    await _pool.close()
    logger.info("database pool closed")
    _pool = None


def get_pool() -> asyncpg.Pool:
    """
    FastAPI dependency: return the active pool.

    Raises `RuntimeError` if the lifespan handler hasn't initialized
    it. This should never happen in normal operation.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool is not initialized. "
            "Ensure the FastAPI lifespan handler called create_pool()."
        )
    return _pool
