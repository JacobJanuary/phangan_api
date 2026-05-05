"""
Process-local cache backed by an OrderedDict (LRU) with TTL.

Suitable as a default for development and single-worker deployments.
For multi-worker / multi-instance deployments swap for a Redis-backed
adapter without touching call sites — they depend on `ICache`.

Implementation notes:
- Eviction policy: LRU (least-recently-used). On capacity overflow we
  evict from the head of the OrderedDict.
- Expiration is checked lazily at `get()` time. Expired entries are
  removed on access; we do not run a background sweeper.
- An `asyncio.Lock` guards mutation. Reads also take the lock to keep
  the LRU order coherent. Contention is negligible for typical
  cache loads.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Entry:
    value: Any
    expires_at: float | None  # monotonic time; None = no expiry


class InMemoryCache:
    """LRU + TTL cache. Implements `ICache`."""

    def __init__(
        self,
        *,
        default_ttl_seconds: int = 300,
        max_entries: int = 5_000,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        if default_ttl_seconds < 0:
            raise ValueError("default_ttl_seconds must be >= 0")

        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and entry.expires_at <= time.monotonic():
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)  # mark as recently used
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl == 0:
            return  # explicit "do not cache"

        expires_at = time.monotonic() + ttl if ttl > 0 else None

        async with self._lock:
            self._store[key] = _Entry(value=value, expires_at=expires_at)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    # ── Introspection (test-only) ────────────────────────────────────

    def size(self) -> int:
        """Current entry count. Snapshot — may race with writers."""
        return len(self._store)
