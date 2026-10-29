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
    to_char(e.start_time, 'HH24:MI') AS event_time,
    to_char(e.start_time, 'HH24:MI') AS start_time,
    to_char(e.end_time, 'HH24:MI') AS end_time,
    e.ends_next_day,
    e.duration,
    e.event_languages,
    e.location_name,
    e.venue_id,
    e.price_thb,
    e.price_kind,
    e.currency_code,
    e.filter_score,
    COALESCE(cover.storage_key, e.image_path) AS image_path,
    COALESCE(media.media, '[]'::jsonb) AS media,
    COALESCE(faqs.faqs, '[]'::jsonb) AS faqs,
    e.source_chat_title,
    e.message_id,
    (SELECT d.username FROM discovered_chats d
      WHERE d.chat_id = e.source_chat_id AND d.username IS NOT NULL
      LIMIT 1) AS source_chat_username,
    e.sender_id,
    NULL::text AS recurrence_type,
    v.name AS venue_name,
    v.name_ru AS venue_name_ru,
    v.lat  AS venue_lat,
    v.lng  AS venue_lng,
    v.google_maps_url AS venue_google_maps_url,
    v.google_rating AS venue_rating,
    v.google_reviews_count AS venue_reviews_count,
    COALESCE(venue_events.events_count, 0)::int AS venue_events_count
"""

_EVENT_JOINS = """
    LEFT JOIN discovery_venues v ON e.venue_id = v.id
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::int AS events_count
        FROM events ve
        WHERE ve.venue_id = e.venue_id
          AND ve.public_status = 'published'
          AND ve.dedup_status = 'unique'
    ) venue_events ON e.venue_id IS NOT NULL
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

_PUBLIC_EVENT_FILTER = """
    e.public_status = 'published'
    AND e.dedup_status = 'unique'
    AND e.enrichment_status <> 'needs_repair'
"""

# Last day of an event: a multi-day one ("9 days", as builders.event_last_date
# reads it) is listed every day until then.
EVENT_LAST_DATE = r"""(e.event_date + (LEAST(GREATEST(COALESCE(
    substring(lower(e.duration) from '(\d+)\s*(?:days?|дн[яей]|день)')::int, 1), 1), 60) - 1))"""
_BKK_TODAY = "(NOW() AT TIME ZONE 'Asia/Bangkok')::date"

# A published event without a start time runs all day (retreat, festival,
# multi-day event): it stays upcoming until its date is over.
_UPCOMING_TIME_FILTER = f"""
    (
        {EVENT_LAST_DATE} > {_BKK_TODAY}
        OR e.start_time IS NULL
        OR CASE
            WHEN e.category ILIKE 'party'
            THEN (e.event_date + e.start_time) + interval '3 hours' >= NOW() AT TIME ZONE 'Asia/Bangkok'
            ELSE (e.event_date + e.start_time) >= NOW() AT TIME ZONE 'Asia/Bangkok'
        END
    )
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
            f"{EVENT_LAST_DATE} >= {_BKK_TODAY}",
            _PUBLIC_EVENT_FILTER,
            _UPCOMING_TIME_FILTER,
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
            conditions.append(f"{_p(today)}::date BETWEEN e.event_date AND {EVENT_LAST_DATE}")
        elif date_filter == "tomorrow":
            conditions.append(f"{_p(tomorrow)}::date BETWEEN e.event_date AND {EVENT_LAST_DATE}")
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
            ORDER BY GREATEST(e.event_date, {_BKK_TODAY}) ASC, e.start_time ASC NULLS LAST,
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
            WHERE e.id = $1 AND {_PUBLIC_EVENT_FILTER}
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
                    INSERT INTO deleted_event_backups (reason, event_id, row_data)
                    SELECT 'phangan_api_delete', e.id, to_jsonb(e)
                    FROM events e
                    WHERE e.id = $1
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
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE events SET image_path = $1 WHERE id = $2",
                    image_path,
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
                    image_path,
                )

    async def get_viewer_gender(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT gender FROM users WHERE id = $1", user_id
            )
