"""
Facepile Service — "Кто пойдёт?"

Two modes:
- Real mode (≥5 right swipes with is_aesthetic faces): show real count + real avatars
- Phantom mode (<5): show random 5-10 count, mix real + phantom avatars

Gender targeting: show opposite-gender avatars predominantly (60-70%).
Mood mapping: match phantom mood to event category.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Media base URL for avatar paths
MEDIA_BASE = "https://media.fastpump.fun"

# ── Mood mapping: event category → phantom mood ─────────────────────────────
CATEGORY_TO_MOOD: dict[str, str] = {
    "party": "party",
    "chill": "spiritual",
    "business": "business",
    "education": "business",
    "sport": "party",
}

# ── In-memory TTL cache ─────────────────────────────────────────────────────
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 60  # seconds


def _cache_key(event_id: int, viewer_gender: str | None) -> str:
    return f"{event_id}:{viewer_gender or 'unknown'}"


def _get_cached(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < CACHE_TTL:
        return entry[1]
    if entry:
        del _cache[key]
    return None


def _set_cache(key: str, value: dict) -> None:
    # Evict old entries if cache grows too large
    if len(_cache) > 5000:
        now = time.time()
        expired = [k for k, (ts, _) in _cache.items() if now - ts > CACHE_TTL]
        for k in expired:
            del _cache[k]
    _cache[key] = (time.time(), value)


def _avatar_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{MEDIA_BASE}/{path}"


async def get_facepile_batch(
    event_ids: list[int],
    event_categories: dict[int, str],
    viewer_gender: str | None,
    pool: asyncpg.Pool,
) -> dict[int, dict]:
    """
    Batch facepile for multiple events in one go.
    Returns: {event_id: {"count": N, "avatarUrls": [...], "is_phantom": bool}}
    """
    if not event_ids:
        return {}

    results: dict[int, dict] = {}
    uncached_ids: list[int] = []

    # 1. Check cache first
    for eid in event_ids:
        key = _cache_key(eid, viewer_gender)
        cached = _get_cached(key)
        if cached is not None:
            results[eid] = cached
        else:
            uncached_ids.append(eid)

    if not uncached_ids:
        return results

    MIN_AVATAR_URLS = 5  # Frontend expects at least 5 avatar circles

    async with pool.acquire() as conn:
        # 2a. Batch query: total right-swipe count per event (ALL users, incl non-aesthetic)
        count_rows = await conn.fetch("""
            SELECT event_id, COUNT(*) as cnt
            FROM user_swipes
            WHERE event_id = ANY($1) AND direction = 'right'
            GROUP BY event_id
        """, uncached_ids)
        total_swipes_by_event = {row["event_id"]: row["cnt"] for row in count_rows}

        # 2b. Batch query: real right-swipe avatars per event (is_aesthetic only)
        real_rows = await conn.fetch("""
            SELECT s.event_id, u.avatar_path, u.gender
            FROM user_swipes s
            JOIN users u ON u.id = s.user_id
            WHERE s.event_id = ANY($1)
              AND s.direction = 'right'
              AND u.is_phantom = false
              AND u.is_aesthetic = true
              AND u.avatar_path IS NOT NULL
            ORDER BY s.event_id, s.swiped_at DESC
        """, uncached_ids)

        # Group by event_id
        real_by_event: dict[int, list[dict]] = {}
        for row in real_rows:
            eid = row["event_id"]
            if eid not in real_by_event:
                real_by_event[eid] = []
            real_by_event[eid].append({
                "avatar_path": row["avatar_path"],
                "gender": row["gender"],
            })

        # 3. Pre-fetch phantom pool (always needed — even real mode may need padding)
        phantom_pool_by_mood: dict[str, list[dict]] = {}
        phantom_rows = await conn.fetch("""
            SELECT id, avatar_path, gender, mood
            FROM users
            WHERE is_phantom = true
              AND avatar_path IS NOT NULL
            ORDER BY RANDOM()
        """)
        for row in phantom_rows:
            mood = row["mood"] or "party"
            if mood not in phantom_pool_by_mood:
                phantom_pool_by_mood[mood] = []
            phantom_pool_by_mood[mood].append({
                "avatar_path": row["avatar_path"],
                "gender": row["gender"],
            })

    def _pick_phantoms(
        needed: int, event_category: str, viewer_g: str | None
    ) -> list[str]:
        """Select gender-biased, mood-matched phantom avatar paths."""
        if needed <= 0:
            return []

        cat = (event_category or "party").lower()
        target_mood = CATEGORY_TO_MOOD.get(cat, "party")

        # Gender targeting
        if viewer_g == "male":
            female_ratio = random.uniform(0.6, 0.7)
        elif viewer_g == "female":
            female_ratio = random.uniform(0.3, 0.4)
        else:
            female_ratio = 0.5

        needed_female = int(needed * female_ratio)
        needed_male = needed - needed_female

        mood_pool = phantom_pool_by_mood.get(target_mood, [])
        fallback_pool = []
        for m, phantoms in phantom_pool_by_mood.items():
            if m != target_mood:
                fallback_pool.extend(phantoms)

        selected: list[str] = []

        females = [p for p in mood_pool if p["gender"] == "female"]
        if len(females) < needed_female:
            females += [p for p in fallback_pool if p["gender"] == "female"]
        random.shuffle(females)
        selected.extend(p["avatar_path"] for p in females[:needed_female])

        males = [p for p in mood_pool if p["gender"] == "male"]
        if len(males) < needed_male:
            males += [p for p in fallback_pool if p["gender"] == "male"]
        random.shuffle(males)
        selected.extend(p["avatar_path"] for p in males[:needed_male])

        return selected

    # 5. Build results for each uncached event
    for eid in uncached_ids:
        real_avatars = real_by_event.get(eid, [])
        total_right = total_swipes_by_event.get(eid, 0)
        cat = event_categories.get(eid, "party")

        real_urls = [_avatar_url(a["avatar_path"]) for a in real_avatars]

        if total_right >= 5:
            # ── REAL MODE: show real count, pad avatars if needed ──
            if len(real_urls) >= MIN_AVATAR_URLS:
                avatar_urls = real_urls[:10]
            else:
                # Pad with phantoms to reach 5 avatar circles
                phantom_paths = _pick_phantoms(
                    MIN_AVATAR_URLS - len(real_urls), cat, viewer_gender
                )
                avatar_urls = real_urls + [_avatar_url(p) for p in phantom_paths]

            result = {
                "count": total_right,
                "avatarUrls": avatar_urls,
                "is_phantom": False,
            }
        else:
            # ── PHANTOM MODE: fake count, mix real + phantoms ──
            target_count = random.randint(5, 10)
            needed_phantoms = max(MIN_AVATAR_URLS, target_count) - len(real_urls)
            phantom_paths = _pick_phantoms(needed_phantoms, cat, viewer_gender)

            all_urls = real_urls + [_avatar_url(p) for p in phantom_paths]
            random.shuffle(all_urls)

            result = {
                "count": target_count,
                "avatarUrls": all_urls[:10],
                "is_phantom": True,
            }

        # Cache
        key = _cache_key(eid, viewer_gender)
        _set_cache(key, result)
        results[eid] = result

    return results

