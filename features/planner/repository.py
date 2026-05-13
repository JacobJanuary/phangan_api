"""SQL repository for the planner feature."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

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


@dataclass(slots=True)
class PlannerRepository:
    pool: asyncpg.Pool

    async def get_user_profile(self, user_id: int) -> asyncpg.Record | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT first_name, gender, mood FROM users WHERE id = $1",
                user_id,
            )

    async def fetch_liked_events_for_date(
        self, *, user_id: int, target_date: date
    ) -> list[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT e.id, e.title, e.summary, e.category,
                       e.event_date, """ + _DISPLAY_TIME_EXPR + """ AS event_time,
                       e.location_name, e.price_thb,
                       v.lat AS venue_lat, v.lng AS venue_lng
                FROM user_swipes s
                JOIN events e ON e.id = s.event_id
                LEFT JOIN discovery_venues v ON e.venue_id = v.id
                WHERE s.user_id = $1
                  AND s.direction = 'right'
                  AND e.event_date = $2
                  AND COALESCE(e.dedup_status, 'unique') = 'unique'
                  AND COALESCE(e.enrichment_status, 'complete') <> 'needs_repair'
                  AND e.start_time IS NOT NULL
                ORDER BY """ + _START_TIME_EXPR + """ ASC NULLS LAST
                """,
                user_id,
                target_date,
            )

    async def fetch_preferences(self, user_id: int) -> list[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT e.category, s.direction, COUNT(*) as cnt
                FROM user_swipes s
                JOIN events e ON e.id = s.event_id
                WHERE s.user_id = $1
                GROUP BY e.category, s.direction
                """,
                user_id,
            )

    async def get_cached_plan(
        self, *, user_id: int, target_date: date
    ) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT input_hash, plan_json
                FROM vibe_pilot_cache
                WHERE user_id = $1 AND target_date = $2
                """,
                user_id,
                target_date,
            )
        if not row:
            return None
        return json.loads(row["plan_json"])

    async def upsert_cached_plan(
        self,
        *,
        user_id: int,
        target_date: date,
        input_hash: str,
        plan: dict,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vibe_pilot_cache (user_id, target_date, input_hash, plan_json)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, target_date)
                DO UPDATE SET input_hash = EXCLUDED.input_hash,
                              plan_json = EXCLUDED.plan_json,
                              created_at = timezone('utc', now())
                """,
                user_id,
                target_date,
                input_hash,
                json.dumps(plan, ensure_ascii=False),
            )
