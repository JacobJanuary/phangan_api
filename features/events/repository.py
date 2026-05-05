"""SQL repository for the events feature."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import asyncpg

from features.events.schemas import EventUpdate

# Common SELECT projection for an event with its venue.
_EVENT_PROJECTION = """
    e.id,
    e.title,
    e.summary,
    e.description,
    e.category,
    e.event_date,
    e.event_time,
    e.location_name,
    e.price_thb,
    e.filter_score,
    e.image_path,
    e.source_chat_title,
    e.sender_id,
    e.recurrence_type,
    v.name AS venue_name,
    v.lat  AS venue_lat,
    v.lng  AS venue_lng,
    COALESCE(e.google_maps_url, v.google_maps_url) AS venue_google_maps_url
"""


@dataclass(slots=True)
class EventsRepository:
    pool: asyncpg.Pool

    async def list_upcoming(
        self,
        *,
        user_id: int,
        category: str,
        date_filter: str,
        today: date,
        tomorrow: date,
        limit: int,
        offset: int,
    ) -> tuple[list[asyncpg.Record], int]:
        conditions: list[str] = [
            "e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date",
            """
            (
                e.event_date > (NOW() AT TIME ZONE 'Asia/Bangkok')::date
                OR NULLIF(e.event_time, '') IS NULL
                OR CASE
                    WHEN e.event_time ~ '^[0-2][0-9]:[0-5][0-9]' THEN
                        CASE WHEN e.category ILIKE 'party'
                             THEN (e.event_date + LEFT(e.event_time, 5)::time) + interval '3 hours' >= NOW() AT TIME ZONE 'Asia/Bangkok'
                             ELSE (e.event_date + LEFT(e.event_time, 5)::time) >= NOW() AT TIME ZONE 'Asia/Bangkok'
                        END
                    ELSE TRUE
                END
            )
            """,
        ]
        params: list[Any] = []

        def _p(val: Any) -> str:
            params.append(val)
            return f"${len(params)}"

        # NOT-already-swiped filter.
        conditions.append(
            f"e.id NOT IN (SELECT event_id FROM user_swipes WHERE user_id = {_p(user_id)})"
        )
        if date_filter == "today":
            conditions.append(f"e.event_date = {_p(today)}")
        elif date_filter == "tomorrow":
            conditions.append(f"e.event_date = {_p(tomorrow)}")
        if category == "party":
            conditions.append(f"e.category = {_p('Party')}")
        elif category == "chill":
            conditions.append(
                f"e.category = ANY({_p(['Chill', 'Sport', 'Education', 'Business'])}::text[])"
            )

        where = "WHERE " + " AND ".join(conditions)
        limit_ph = _p(limit)
        offset_ph = _p(offset)

        query = f"""
            SELECT
                COUNT(*) OVER() AS total_count,
                {_EVENT_PROJECTION}
            FROM events e
            LEFT JOIN venues v ON e.venue_id = v.id
            {where}
            ORDER BY e.event_date ASC, e.event_time ASC NULLS LAST,
                     e.filter_score DESC NULLS LAST
            LIMIT {limit_ph} OFFSET {offset_ph}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        total = rows[0]["total_count"] if rows else 0
        return rows, int(total)

    async def get_one(self, event_id: int) -> asyncpg.Record | None:
        query = f"""
            SELECT {_EVENT_PROJECTION}
            FROM events e
            LEFT JOIN venues v ON e.venue_id = v.id
            WHERE e.id = $1
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, event_id)

    async def get_owner_telegram_id(self, event_id: int) -> int | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT sender_id FROM events WHERE id = $1", event_id
            )

    async def update_owned(
        self, event_id: int, payload: EventUpdate
    ) -> bool:
        """Apply partial update. Returns True if any field was updated."""
        update_fields: list[str] = []
        params: list[Any] = []
        idx = 1

        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is None and field != "recurrence_type":
                continue
            if field in ("title", "summary", "description"):
                update_fields.append(
                    f"{field} = COALESCE({field}, '{{}}') || ${idx}::jsonb"
                )
                params.append(json.dumps(value, ensure_ascii=False))
            elif field == "event_date":
                update_fields.append(f"{field} = ${idx}")
                params.append(date.fromisoformat(value))
            else:
                update_fields.append(f"{field} = ${idx}")
                params.append(value)
            idx += 1

        if not update_fields:
            return False

        params.append(event_id)
        query = f"""
            UPDATE events
            SET {', '.join(update_fields)}
            WHERE id = ${idx}
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, *params)
        return True

    async def delete_with_dependencies(self, event_id: int) -> None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM user_swipes WHERE event_id = $1", event_id
                )
                await conn.execute(
                    "DELETE FROM outreach_log WHERE event_id = $1", event_id
                )
                await conn.execute("DELETE FROM events WHERE id = $1", event_id)

    async def get_image_metadata(
        self, event_id: int
    ) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT sender_id, category, image_path
                FROM events WHERE id = $1
                """,
                event_id,
            )
        return dict(row) if row else None

    async def set_image_path(self, event_id: int, image_path: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE events SET image_path = $1 WHERE id = $2",
                image_path,
                event_id,
            )

    async def get_viewer_gender(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT gender FROM users WHERE id = $1", user_id
            )
