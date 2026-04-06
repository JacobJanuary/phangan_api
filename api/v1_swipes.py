"""
Swipes V1 API — My Vibe: swipe persistence & personalized feed.

POST /api/v1/swipes        — save a swipe (fire-and-forget)
GET  /api/v1/swipes/my-vibe — upcoming + paginated past right-swiped events
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.core.dependencies import get_current_user_id
from app.db.database import get_pool
from app.schemas.swipe import SwipeCreate

# Reuse the event builder from v1_events
from app.api.v1_events import _build_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/swipes", tags=["swipes"])

BKK = ZoneInfo("Asia/Bangkok")


# ── POST /api/v1/swipes ─────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def save_swipe(
    body: SwipeCreate,
    pool: asyncpg.Pool = Depends(get_pool),
    user_id: int = Depends(get_current_user_id),
) -> Response:
    """Persist a left/right swipe. Idempotent via ON CONFLICT."""
    query = """
        INSERT INTO user_swipes (user_id, event_id, direction, swiped_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id, event_id)
        DO UPDATE SET direction = $3, swiped_at = NOW()
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(query, user_id, body.event_id, body.direction)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    except Exception as exc:
        logger.error("Error saving swipe for user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save swipe",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── GET /api/v1/swipes/my-vibe ──────────────────────────────────────────────

# Same time-based visibility rules as the main events feed
_UPCOMING_TIME_FILTER = """
    (
        e.event_date > (NOW() AT TIME ZONE 'Asia/Bangkok')::date
        OR NULLIF(e.event_time, '') IS NULL
        OR (
            e.category ILIKE 'party' AND
            (e.event_date + LEFT(e.event_time, 5)::time) + interval '3 hours' >= NOW() AT TIME ZONE 'Asia/Bangkok'
        )
        OR (
            e.category NOT ILIKE 'party' AND
            (e.event_date + LEFT(e.event_time, 5)::time) >= NOW() AT TIME ZONE 'Asia/Bangkok'
        )
    )
"""


@router.get("/my-vibe")
async def my_vibe(
    lang: Literal["en", "ru"] = Query(default="ru"),
    include_past: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Return the user's right-swiped events, split into upcoming & past."""
    now_bkk = datetime.now(BKK)
    today = now_bkk.date()
    tomorrow = date.fromordinal(today.toordinal() + 1)

    _EVENT_COLUMNS = """
        e.id, e.title, e.summary, e.description, e.category,
        e.event_date, e.event_time, e.location_name, e.price_thb,
        e.filter_score, e.image_path, e.source_chat_title,
        v.name AS venue_name, v.lat AS venue_lat, v.lng AS venue_lng,
        v.google_maps_url AS venue_google_maps_url,
        s.swiped_at
    """

    _FROM_JOIN = """
        FROM user_swipes s
        JOIN events e ON e.id = s.event_id
        LEFT JOIN venues v ON e.venue_id = v.id
    """

    _BASE_WHERE = "WHERE s.user_id = $1 AND s.direction = 'right'"

    # ── 1. Upcoming right-swiped events (all, no pagination) ─────────────
    upcoming_query = f"""
        SELECT {_EVENT_COLUMNS}
        {_FROM_JOIN}
        {_BASE_WHERE}
        AND e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date
        AND {_UPCOMING_TIME_FILTER}
        ORDER BY e.event_date ASC, e.event_time ASC NULLS LAST
    """

    # ── 2. Past total count ──────────────────────────────────────────────
    past_count_query = f"""
        SELECT COUNT(*)
        {_FROM_JOIN}
        {_BASE_WHERE}
        AND NOT (
            e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date
            AND {_UPCOMING_TIME_FILTER}
        )
    """

    try:
        async with pool.acquire() as conn:
            upcoming_rows = await conn.fetch(upcoming_query, user_id)
            past_total = await conn.fetchval(past_count_query, user_id)

            upcoming = []
            for r in upcoming_rows:
                ev = _build_event(r, lang, today, tomorrow, now_bkk)
                ev["swiped_at"] = r["swiped_at"].isoformat() if r["swiped_at"] else None
                upcoming.append(ev)

            result: dict[str, Any] = {
                "upcoming": upcoming,
                "past_total": past_total or 0,
            }

            # ── 3. Past events (paginated, only if requested) ────────────
            if include_past:
                past_query = f"""
                    SELECT {_EVENT_COLUMNS}
                    {_FROM_JOIN}
                    {_BASE_WHERE}
                    AND NOT (
                        e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date
                        AND {_UPCOMING_TIME_FILTER}
                    )
                    ORDER BY e.event_date DESC, e.event_time DESC NULLS LAST
                    LIMIT $2 OFFSET $3
                """
                past_rows = await conn.fetch(past_query, user_id, limit, offset)
                past = []
                for r in past_rows:
                    ev = _build_event(r, lang, today, tomorrow, now_bkk)
                    ev["swiped_at"] = r["swiped_at"].isoformat() if r["swiped_at"] else None
                    past.append(ev)
                result["past"] = past

        # ── Enrich all events with facepile avatars ("Кто пойдёт?") ──────
        all_events = upcoming + result.get("past", [])
        if all_events:
            try:
                from app.services.facepile_service import get_facepile_batch

                viewer_gender = None
                try:
                    async with pool.acquire() as conn:
                        viewer_gender = await conn.fetchval(
                            "SELECT gender FROM users WHERE id = $1", user_id
                        )
                except Exception:
                    pass

                event_ids = [int(ev["id"]) for ev in all_events]
                event_categories = {int(ev["id"]): ev.get("category", "") for ev in all_events}

                facepile_data = await get_facepile_batch(
                    event_ids, event_categories, viewer_gender, pool
                )
                for ev in all_events:
                    fp = facepile_data.get(int(ev["id"]))
                    if fp:
                        ev["attendeeCount"] = fp["count"]
                        ev["facepileUrls"] = fp["avatarUrls"]
            except Exception as exc:
                logger.warning("Facepile enrichment failed for my-vibe: %s", exc)

    except Exception as exc:
        logger.error("Error fetching my-vibe for user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch vibe feed",
        )

    return result


# ── DELETE /api/v1/swipes/reset ──────────────────────────────────────────────

@router.delete("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_swipes(
    pool: asyncpg.Pool = Depends(get_pool),
    user_id: int = Depends(get_current_user_id),
) -> Response:
    """Delete ALL swipes for the current user (debug/QA only)."""
    try:
        async with pool.acquire() as conn:
            deleted = await conn.execute(
                "DELETE FROM user_swipes WHERE user_id = $1", user_id
            )
            logger.info("Reset swipes for user %d: %s", user_id, deleted)
    except Exception as exc:
        logger.error("Error resetting swipes for user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset swipes",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
