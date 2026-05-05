"""IP-based intrusion tracking.

Lightweight in-memory tracker: counts strikes per IP and blacklists after
a configurable threshold. Swappable for Redis later via the `IPTracker`
Protocol.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class IPTracker(Protocol):
    """Interface for tracking and blacklisting abusive IPs."""

    def record_failure(self, ip: str) -> None: ...
    def is_blacklisted(self, ip: str) -> bool: ...
    def get_strikes(self, ip: str) -> int: ...


class InMemoryIPTracker:
    """In-memory tracker with a configurable strike limit."""

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
                "IP blacklisted",
                extra={"ip": ip, "strikes": self._strikes[ip]},
            )

    def is_blacklisted(self, ip: str) -> bool:
        return ip in self._blacklist

    def get_strikes(self, ip: str) -> int:
        return self._strikes.get(ip, 0)


_tracker_instance: InMemoryIPTracker | None = None


def get_ip_tracker(settings: Settings | None = None) -> IPTracker:
    global _tracker_instance  # noqa: PLW0603
    if _tracker_instance is None:
        cfg = settings or get_settings()
        _tracker_instance = InMemoryIPTracker(strike_limit=cfg.IP_STRIKE_LIMIT)
    return _tracker_instance
