"""
Security — API Key validation and IP-based intrusion tracking.

Components:
  - IPTracker (Protocol)    — abstract interface for strike tracking
  - InMemoryIPTracker       — concrete in-memory implementation (swap to Redis later)
  - verify_api_key          — FastAPI dependency for header-based auth
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# IP Tracker — abstract interface
# ---------------------------------------------------------------------------
@runtime_checkable
class IPTracker(Protocol):
    """Interface for tracking and blacklisting abusive IPs."""

    def record_failure(self, ip: str) -> None:
        """Record an auth failure from *ip*. Blacklist after threshold."""
        ...

    def is_blacklisted(self, ip: str) -> bool:
        """Return True if *ip* is blacklisted."""
        ...

    def get_strikes(self, ip: str) -> int:
        """Return current strike count for *ip*."""
        ...


# ---------------------------------------------------------------------------
# Concrete in-memory implementation
# ---------------------------------------------------------------------------
class InMemoryIPTracker:
    """
    In-memory IP tracker with a configurable strike limit.

    To replace with Redis:
    1. Create a RedisIPTracker implementing IPTracker.
    2. Swap the instance in get_ip_tracker().
    """

    def __init__(self, strike_limit: int = 3) -> None:
        self._strike_limit = strike_limit
        self._strikes: dict[str, int] = {}
        self._blacklist: set[str] = set()

    def record_failure(self, ip: str) -> None:
        if ip in self._blacklist:
            return
        self._strikes[ip] = self._strikes.get(ip, 0) + 1
        if self._strikes[ip] >= self._strike_limit:
            self._blacklist.add(ip)
            logger.warning(
                "🚫 IP BLACKLISTED: %s (after %d failed attempts)",
                ip,
                self._strikes[ip],
            )

    def is_blacklisted(self, ip: str) -> bool:
        return ip in self._blacklist

    def get_strikes(self, ip: str) -> int:
        return self._strikes.get(ip, 0)


# ---------------------------------------------------------------------------
# Singleton tracker instance
# ---------------------------------------------------------------------------
_tracker_instance: InMemoryIPTracker | None = None


def get_ip_tracker() -> IPTracker:
    """Return the global IP tracker (lazily initialized)."""
    global _tracker_instance  # noqa: PLW0603
    if _tracker_instance is None:
        settings = get_settings()
        _tracker_instance = InMemoryIPTracker(strike_limit=settings.IP_STRIKE_LIMIT)
    return _tracker_instance


# ---------------------------------------------------------------------------
# FastAPI dependency — API key verification
# ---------------------------------------------------------------------------
async def verify_api_key(
    request: Request,
    api_key: str | None = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validate the X-API-Key header.

    On failure, records a strike against the client IP.
    Raises 401 Unauthorized on invalid key.
    """
    tracker = get_ip_tracker()
    client_ip = request.client.host if request.client else "unknown"

    if not api_key or api_key != settings.API_KEY:
        tracker.record_failure(client_ip)
        strikes = tracker.get_strikes(client_ip)
        logger.warning(
            "⚠️  Invalid API key from %s (strike %d/%d)",
            client_ip,
            strikes,
            settings.IP_STRIKE_LIMIT,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

    return api_key
