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
    e.public_status = 'published'
    AND COALESCE(e.dedup_status, 'unique') = 'unique'
    AND COALESCE(e.enrichment_status, 'complete') <> 'needs_repair'
    AND e.start_time IS NOT NULL
"""

# Common SELECT projection for an event with its venue.
_EVENT_PROJECTION = f"""
    e.id,
    e.public_id,
    e.slug,
    e.title,
    e.summary,
    e.description,
    e.sharing_description,
    e.requirements,
    e.keywords,
    e.demographic_filters,
    e.ai_addons,
    e.capacity,
    e.metadata_status,
    e.public_status,
    e.timezone,
    e.category,
    e.event_type,
    e.event_category,
    e.event_sub_category,
    e.event_date,
    {_DISPLAY_TIME_EXPR} AS event_time,
    e.start_time,
    e.end_time,
    e.ends_next_day,
    e.location_name,
    e.price_thb,
    e.currency_code,
    e.filter_score,
    COALESCE(cover.storage_key, e.image_path) AS image_path,
    COALESCE(media.media, '[]'::jsonb) AS media,
    COALESCE(faqs.faqs, '[]'::jsonb) AS faqs,
    e.source_chat_title,
    e.sender_id,
    NULL::text AS recurrence_type,
    v.name AS venue_name,
    v.lat  AS venue_lat,
    v.lng  AS venue_lng,
    v.google_maps_url AS venue_google_maps_url
"""

_EVENT_JOINS = """
    LEFT JOIN discovery_venues v ON e.venue_id = v.id
    LEFT JOIN LATERAL (
        SELECT em.storage_key
        FROM event_media em
        WHERE em.event_id = e.id
        ORDER BY em.is_cover DESC, em.sort_order ASC, em.id ASC
        LIMIT 1
    ) cover ON true
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(
            jsonb_build_object(
                'id', em.id,
                'type', em.media_type,
                'storage_key', em.storage_key,
                'source_url', em.source_url,
                'sort_order', em.sort_order,
                'is_cover', em.is_cover,
                'metadata', em.metadata
            )
            ORDER BY em.is_cover DESC, em.sort_order ASC, em.id ASC
        ) AS media
        FROM event_media em
        WHERE em.event_id = e.id
    ) media ON true
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(
            jsonb_build_object(
                'id', f.id,
                'question', f.question,
                'answer', f.answer,
                'sort_order', f.sort_order
            )
            ORDER BY f.sort_order ASC, f.id ASC
        ) AS faqs
        FROM event_faqs f
        WHERE f.event_id = e.id
    ) faqs ON true
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
            {_EVENT_JOINS}
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
            {_EVENT_JOINS}
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
        payload_data = payload.model_dump(exclude_unset=True)
        faqs = payload_data.pop("faqs", None)

        for field, value in payload_data.items():
            if value is None:
                continue
            if field in (
                "title",
                "summary",
                "description",
                "sharing_description",
                "requirements",
                "keywords",
                "demographic_filters",
            ):
                update_fields.append(
                    f"{field} = COALESCE({field}, '{{}}') || ${idx}::jsonb"
                )
                params.append(json.dumps(value, ensure_ascii=False))
            elif field == "ai_addons":
                update_fields.append(
                    f"{field} = COALESCE({field}, '[]'::jsonb) || ${idx}::jsonb"
                )
                params.append(json.dumps(value, ensure_ascii=False))
            elif field == "event_date":
                update_fields.append(f"{field} = ${idx}")
                params.append(date.fromisoformat(value))
            elif field in ("start_time", "end_time"):
                update_fields.append(f"{field} = ${idx}")
                params.append(_parse_time_token(value))
            else:
                update_fields.append(f"{field} = ${idx}")
                params.append(value)
            idx += 1

        if not update_fields and faqs is None:
            return False

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if update_fields:
                    params.append(event_id)
                    query = f"""
                        UPDATE events
                        SET {', '.join(update_fields)}
                        WHERE id = ${idx}
                    """
                    await conn.execute(query, *params)
                if faqs is not None:
                    await conn.execute("DELETE FROM event_faqs WHERE event_id = $1", event_id)
                    for sort_order, faq in enumerate(faqs):
                        question = faq.get("question") if isinstance(faq, dict) else None
                        answer = faq.get("answer") if isinstance(faq, dict) else None
                        if not question or not answer:
                            continue
                        await conn.execute(
                            """
                            INSERT INTO event_faqs (event_id, question, answer, sort_order)
                            VALUES ($1, $2::jsonb, $3::jsonb, $4)
                            """,
                            event_id,
                            json.dumps(question, ensure_ascii=False),
                            json.dumps(answer, ensure_ascii=False),
                            sort_order,
                        )
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
            async with conn.transaction():
                await conn.execute(
                    "UPDATE events SET image_path = $1 WHERE id = $2",
                    safe_path,
                    event_id,
                )
                await conn.execute(
                    "UPDATE event_media SET is_cover = false WHERE event_id = $1",
                    event_id,
                )
                await conn.execute(
                    """
                    INSERT INTO event_media (event_id, media_type, storage_key, sort_order, is_cover, metadata)
                    VALUES ($1, 'image', $2, 0, true, '{"source":"phangan_api_upload"}'::jsonb)
                    ON CONFLICT (event_id, storage_key)
                    DO UPDATE SET is_cover = true,
                                  sort_order = 0,
                                  updated_at = timezone('utc', now())
                    """,
                    event_id,
                    safe_path,
                )

    async def get_viewer_gender(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT gender FROM users WHERE id = $1", user_id
            )
