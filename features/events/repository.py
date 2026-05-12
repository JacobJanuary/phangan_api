"""SQL repository for the events feature."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, time
from typing import Any

import asyncpg

from features.events.schemas import EventUpdate
from shared.media.urls import safe_relative_media_path

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

_PUBLIC_EVENT_FILTER = """
    COALESCE(e.dedup_status, 'unique') = 'unique'
    AND COALESCE(e.enrichment_status, 'complete') <> 'needs_repair'
"""

# Common SELECT projection for an event with its venue.
_EVENT_PROJECTION = f"""
    e.id,
    e.title,
    e.summary,
    e.description,
    e.category,
    e.event_date,
    {_DISPLAY_TIME_EXPR} AS event_time,
    e.start_time,
    e.end_time,
    e.ends_next_day,
    e.location_name,
    e.price_thb,
    e.filter_score,
    e.image_path,
    e.source_chat_title,
    e.sender_id,
    NULL::text AS recurrence_type,
    v.name AS venue_name,
    v.lat  AS venue_lat,
    v.lng  AS venue_lng,
    v.google_maps_url AS venue_google_maps_url
"""


def _parse_time_token(raw: str | None) -> time | None:
    if not raw:
        return None
    text = raw.strip()[:5]
    try:
        hour, minute = [int(part) for part in text.split(":", 1)]
    except Exception:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour, minute)


def _parse_time_range(raw: str | None) -> tuple[time | None, time | None, bool]:
    if not raw:
        return None, None, False
    if "-" in raw:
        left, right = raw.split("-", 1)
        start = _parse_time_token(left)
        end = _parse_time_token(right)
    else:
        start = _parse_time_token(raw)
        end = None
    return start, end, bool(start and end and end <= start)


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
            _PUBLIC_EVENT_FILTER,
            """
            (
                e.event_date > (NOW() AT TIME ZONE 'Asia/Bangkok')::date
                OR ({start_time}) IS NULL
                OR CASE
                    WHEN e.category ILIKE 'party'
                    THEN (e.event_date + ({start_time})) + interval '3 hours' >= NOW() AT TIME ZONE 'Asia/Bangkok'
                    ELSE (e.event_date + ({start_time})) >= NOW() AT TIME ZONE 'Asia/Bangkok'
                END
            )
            """.format(start_time=_START_TIME_EXPR),
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
            # Match builders.PARTY_CATEGORIES — case-insensitive.
            conditions.append(
                f"LOWER(e.category) = ANY({_p(['party', 'concert', 'dance', 'ecstatic_dance'])}::text[])"
            )
        elif category == "chill":
            # Everything not in the party allow-list, including NULL/empty.
            conditions.append(
                f"(LOWER(COALESCE(e.category, '')) <> ALL({_p(['party', 'concert', 'dance', 'ecstatic_dance'])}::text[]))"
            )

        where = "WHERE " + " AND ".join(conditions)
        limit_ph = _p(limit)
        offset_ph = _p(offset)

        query = f"""
            SELECT
                COUNT(*) OVER() AS total_count,
                {_EVENT_PROJECTION}
            FROM events e
            LEFT JOIN discovery_venues v ON e.venue_id = v.id
            {where}
            ORDER BY e.event_date ASC, ({_START_TIME_EXPR}) ASC NULLS LAST,
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
            LEFT JOIN discovery_venues v ON e.venue_id = v.id
            WHERE e.id = $1
              AND {_PUBLIC_EVENT_FILTER}
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
            elif field == "event_time":
                start, end, ends_next_day = _parse_time_range(value)
                update_fields.append(
                    f"start_time = ${idx}, end_time = ${idx + 1}, "
                    f"ends_next_day = ${idx + 2}"
                )
                params.extend([start, end, ends_next_day])
                idx += 3
                continue
            elif field == "google_maps_url":
                # Deprecated denormalized field. Canonical maps URL belongs to discovery_venues.
                continue
            elif field == "recurrence_type":
                # Recurrence is owned by parser-side copy logic; this API does not write it.
                continue
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
                    """
                    INSERT INTO deleted_event_backups (event_id, row_data, reason)
                    SELECT id, to_jsonb(events.*), 'phangan_api_delete'
                    FROM events
                    WHERE id = $1
                    """,
                    event_id,
                )
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
        safe_path = safe_relative_media_path(image_path)
        if safe_path is None:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE events SET image_path = $1 WHERE id = $2",
                safe_path,
                event_id,
            )

    async def get_viewer_gender(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT gender FROM users WHERE id = $1", user_id
            )
