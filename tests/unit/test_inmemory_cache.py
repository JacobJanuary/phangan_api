"""Unit tests for `shared.cache.memory_adapter.InMemoryCache`."""

from __future__ import annotations

import asyncio
import time

import pytest

from shared.cache import ICache, InMemoryCache


def test_inmemory_cache_satisfies_protocol() -> None:
    cache = InMemoryCache()
    assert isinstance(cache, ICache)


def test_invalid_construction_args() -> None:
    with pytest.raises(ValueError):
        InMemoryCache(max_entries=0)
    with pytest.raises(ValueError):
        InMemoryCache(default_ttl_seconds=-1)


@pytest.mark.asyncio
async def test_set_then_get_returns_value() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v")
    assert await cache.get("k") == "v"


@pytest.mark.asyncio
async def test_get_missing_returns_none() -> None:
    cache = InMemoryCache()
    assert await cache.get("missing") is None


@pytest.mark.asyncio
async def test_explicit_zero_ttl_skips_storage() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v", ttl_seconds=0)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_expired_entry_is_evicted_on_get(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = InMemoryCache(default_ttl_seconds=1)
    await cache.set("k", "v")

    # advance the monotonic clock past the TTL
    base = time.monotonic()
    monkeypatch.setattr(
        "shared.cache.memory_adapter.time.monotonic", lambda: base + 2
    )
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_lru_eviction_when_over_capacity() -> None:
    cache = InMemoryCache(max_entries=2)
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.get("a")  # touch "a" so "b" becomes the LRU
    await cache.set("c", 3)

    assert await cache.get("b") is None  # evicted
    assert await cache.get("a") == 1
    assert await cache.get("c") == 3


@pytest.mark.asyncio
async def test_delete_removes_entry() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v")
    await cache.delete("k")
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_clear_drops_all_entries() -> None:
    cache = InMemoryCache()
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.clear()
    assert cache.size() == 0


@pytest.mark.asyncio
async def test_concurrent_writes_do_not_corrupt_state() -> None:
    cache = InMemoryCache(max_entries=100)

    async def writer(prefix: str) -> None:
        for i in range(50):
            await cache.set(f"{prefix}{i}", i)

    await asyncio.gather(writer("a"), writer("b"))
    # 100 unique keys, capacity 100 -> all should fit
    assert cache.size() == 100
