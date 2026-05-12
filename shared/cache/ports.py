"""
Cache port.

Implementations live in adapter modules in the same package. Use
cases and services should accept `ICache` via constructor injection
and not import any concrete implementation.

The contract is intentionally minimal — get / set / delete / clear.
Caches are best-effort: a `get` miss is not an error, and `set` may
silently evict older entries.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ICache(Protocol):
    """Generic key/value cache with optional TTL."""

    async def get(self, key: str) -> Any | None:
        """
        Return the cached value, or None if missing or expired.

        Implementations MUST NOT raise on a miss; they MAY raise on
        connectivity failures (e.g. Redis), in which case the caller
        decides whether to fall back to recomputation.
        """
        ...

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Store `value` under `key`.

        If `ttl_seconds` is None, fall back to the adapter's default
        TTL. A TTL of 0 means "do not store" (useful for conditional
        caching).
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove the key. No-op if missing."""
        ...

    async def clear(self) -> None:
        """Drop every entry. Used in tests and admin tooling."""
        ...
