"""SQL repository for swipes."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

_START_TIME_EXPR = """
    e.start_time
"""

_DISPLAY_TIME_EXPR = """
    CASE
        WHEN e.start_time IS NOT NULL AND e.end_time IS NOT NULL THEN
            to_char(e.start_time, 'HH24:MI') || ' - ' || to_char(e.end_time, 'HH24:MI')
        WHEN e.start_time IS NOT NULL THEN to_char(e.start_time, 'HH24:MI')
        ELSE NULL
    END
"""

# WHERE clauses shared between upcoming/past splits.
_UPCOMING_TIME_FILTER = f"""
    (
        e.event_date > (NOW() AT TIME ZONE 'Asia/Bangkok')::date
        OR CASE
            WHEN e.category ILIKE 'party'
            THEN (e.event_date + ({_START_TIME_EXPR})) + interval '3 hours' >= NOW() AT TIME ZONE 'Asia/Bangkok'
            ELSE (e.event_date + ({_START_TIME_EXPR})) >= NOW() AT TIME ZONE 'Asia/Bangkok'
        END
    )
"""

_EVENT_COLUMNS = f"""
    e.id, e.title, e.summary, e.description, e.category,
    e.event_date, {_DISPLAY_TIME_EXPR} AS event_time, e.location_name, e.price_thb,
    e.filter_score, e.image_path, e.source_chat_title, e.sender_id,
    NULL::text AS recurrence_type,
    v.name AS venue_name, v.lat AS venue_lat, v.lng AS venue_lng,
    v.google_maps_url AS venue_google_maps_url,
    s.swiped_at
"""

_FROM_JOIN = """
    FROM user_swipes s
    JOIN events e ON e.id = s.event_id
    LEFT JOIN discovery_venues v ON e.venue_id = v.id
"""

_BASE_WHERE = """
    WHERE s.user_id = $1
      AND s.direction = 'right'
      AND COALESCE(e.dedup_status, 'unique') = 'unique'
      AND COALESCE(e.enrichment_status, 'complete') <> 'needs_repair'
      AND e.start_time IS NOT NULL
"""


@dataclass(slots=True)
class SwipesRepository:
    pool: asyncpg.Pool

    async def upsert_swipe(
        self, *, user_id: int, event_id: int, direction: str
    ) -> None:
        """Idempotent insert via ON CONFLICT.

        Raises asyncpg.ForeignKeyViolationError if the event_id is invalid.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_swipes (user_id, event_id, direction, swiped_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id, event_id)
                DO UPDATE SET direction = $3, swiped_at = NOW()
                """,
                user_id,
                event_id,
                direction,
            )

    async def fetch_upcoming(self, user_id: int) -> list[asyncpg.Record]:
        query = f"""
            SELECT {_EVENT_COLUMNS}
            {_FROM_JOIN}
            {_BASE_WHERE}
            AND e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date
            AND {_UPCOMING_TIME_FILTER}
            ORDER BY e.event_date ASC, ({_START_TIME_EXPR}) ASC NULLS LAST
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, user_id)

    async def count_past(self, user_id: int) -> int:
        query = f"""
            SELECT COUNT(*)
            {_FROM_JOIN}
            {_BASE_WHERE}
            AND NOT (
                e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date
                AND {_UPCOMING_TIME_FILTER}
            )
        """
        async with self.pool.acquire() as conn:
            return int(await conn.fetchval(query, user_id) or 0)

    async def fetch_past(
        self, user_id: int, *, limit: int, offset: int
    ) -> list[asyncpg.Record]:
        query = f"""
            SELECT {_EVENT_COLUMNS}
            {_FROM_JOIN}
            {_BASE_WHERE}
            AND NOT (
                e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date
                AND {_UPCOMING_TIME_FILTER}
            )
            ORDER BY e.event_date DESC, ({_START_TIME_EXPR}) DESC NULLS LAST
            LIMIT $2 OFFSET $3
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, user_id, limit, offset)

    async def reset_for_user(self, user_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_swipes WHERE user_id = $1", user_id
            )
