"""Facepile orchestrator — combines repository + selector + TTL cache.

Preserves the legacy contract verbatim:
- Real mode (>= 5 right swipes): show true count + real avatars (padded with
  phantoms if fewer than 5 aesthetic faces are available).
- Phantom mode (< 5): show a fake count between 5 and 10, mix real + phantoms,
  cap output at 10 avatars.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import TypedDict

import asyncpg

from shared.facepile.repository import FacepileRepository
from shared.facepile.selector import pick_phantoms

logger = logging.getLogger(__name__)


class FacepileResult(TypedDict):
    count: int
    avatarUrls: list[str | None]
    is_phantom: bool


_MIN_AVATAR_URLS = 5  # Frontend always renders at least 5 circles.
_MAX_AVATAR_URLS = 10
_REAL_MODE_THRESHOLD = 5  # >= this many right swipes triggers real mode.
_DEFAULT_CACHE_TTL_S = 60
_DEFAULT_CACHE_MAX = 5000


def _avatar_url(media_base_url: str, path: str | None) -> str | None:
    if not path:
        return None
    return f"{media_base_url.rstrip('/')}/{path}"


@dataclass(slots=True)
class _CacheEntry:
    value: FacepileResult
    ts: float


@dataclass(slots=True)
class FacepileService:
    """Compose `count + avatarUrls + is_phantom` for a batch of events."""

    pool: asyncpg.Pool
    media_base_url: str
    cache_ttl_s: int = _DEFAULT_CACHE_TTL_S
    cache_max_size: int = _DEFAULT_CACHE_MAX
    rng: random.Random = field(default_factory=random.Random)
    _cache: dict[str, _CacheEntry] = field(default_factory=dict, init=False)

    @staticmethod
    def _key(event_id: int, viewer_gender: str | None) -> str:
        return f"{event_id}:{viewer_gender or 'unknown'}"

    def _get_cached(self, key: str) -> FacepileResult | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.ts >= self.cache_ttl_s:
            del self._cache[key]
            return None
        return entry.value

    def _set_cache(self, key: str, value: FacepileResult) -> None:
        if len(self._cache) > self.cache_max_size:
            now = time.time()
            expired = [
                k
                for k, e in self._cache.items()
                if now - e.ts >= self.cache_ttl_s
            ]
            for k in expired:
                del self._cache[k]
        self._cache[key] = _CacheEntry(value=value, ts=time.time())

    async def get_batch(
        self,
        *,
        event_ids: list[int],
        event_categories: dict[int, str],
        viewer_gender: str | None,
    ) -> dict[int, FacepileResult]:
        if not event_ids:
            return {}

        results: dict[int, FacepileResult] = {}
        uncached: list[int] = []
        for eid in event_ids:
            cached = self._get_cached(self._key(eid, viewer_gender))
            if cached is not None:
                results[eid] = cached
            else:
                uncached.append(eid)

        if not uncached:
            return results

        repo = FacepileRepository(pool=self.pool)
        totals = await repo.count_right_swipes_per_event(uncached)
        attendees = await repo.aesthetic_real_attendees(uncached)
        phantom_pool = await repo.phantom_pool_by_mood()

        real_by_event: dict[int, list[str]] = {}
        for att in attendees:
            real_by_event.setdefault(att.event_id, []).append(att.avatar_path)

        for eid in uncached:
            real_paths = real_by_event.get(eid, [])
            real_urls: list[str | None] = [
                _avatar_url(self.media_base_url, p) for p in real_paths
            ]
            total_right = totals.get(eid, 0)
            cat = event_categories.get(eid, "party")

            if total_right >= _REAL_MODE_THRESHOLD:
                if len(real_urls) >= _MIN_AVATAR_URLS:
                    avatars = real_urls[:_MAX_AVATAR_URLS]
                else:
                    pad = pick_phantoms(
                        needed=_MIN_AVATAR_URLS - len(real_urls),
                        event_category=cat,
                        viewer_gender=viewer_gender,
                        pool_by_mood=phantom_pool,
                        rng=self.rng,
                    )
                    avatars = real_urls + [
                        _avatar_url(self.media_base_url, p) for p in pad
                    ]
                result: FacepileResult = {
                    "count": total_right,
                    "avatarUrls": avatars,
                    "is_phantom": False,
                }
            else:
                target_count = self.rng.randint(5, 10)
                needed_phantoms = (
                    max(_MIN_AVATAR_URLS, target_count) - len(real_urls)
                )
                pad = pick_phantoms(
                    needed=needed_phantoms,
                    event_category=cat,
                    viewer_gender=viewer_gender,
                    pool_by_mood=phantom_pool,
                    rng=self.rng,
                )
                all_urls: list[str | None] = real_urls + [
                    _avatar_url(self.media_base_url, p) for p in pad
                ]
                self.rng.shuffle(all_urls)
                result = {
                    "count": target_count,
                    "avatarUrls": all_urls[:_MAX_AVATAR_URLS],
                    "is_phantom": True,
                }

            self._set_cache(self._key(eid, viewer_gender), result)
            results[eid] = result

        return results
