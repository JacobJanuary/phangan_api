"""
Events V1 API — JWT-protected, frontend-ready event listing.

GET /api/v1/events
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user_id
from app.db.database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events-v1"])

# ── Constants ────────────────────────────────────────────────────────────────
MEDIA_BASE = "https://api.fastpump.fun/api/media"

# Chill-family categories that map to type="chill"
CHILL_CATEGORIES = {"chill", "sport", "education", "business"}

# Color palette
TYPE_COLOR = {"party": "#ff007f", "chill": "#00f3ff"}

# Abbreviated weekday + month names (en / ru)
_WEEKDAYS_EN = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_WEEKDAYS_RU = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
_MONTHS_EN   = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MONTHS_RU   = ["ЯНВ", "ФЕВ", "МАР", "АПР", "МАЙ", "ИЮН",
                "ИЮЛ", "АВГ", "СЕН", "ОКТ", "НОЯ", "ДЕК"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_text(jsonb_val: Any, lang: str) -> str:
    """Extract localized text from a JSONB dict. Falls back ru→en or empty."""
    import json
    if not jsonb_val:
        return ""
        
    parsed = jsonb_val
    if isinstance(jsonb_val, str):
        try:
            parsed = json.loads(jsonb_val)
        except Exception:
            # If it's just a raw string, return it as-is
            return jsonb_val
            
    if isinstance(parsed, dict):
        return parsed.get(lang) or parsed.get("ru") or parsed.get("en") or ""
        
    return str(parsed)


def _date_info(ev_date: date | None, lang: str, today: date, tomorrow: date) -> tuple[str, str]:
    """Return (dateInfo label, dateCategory bucket) for an event date."""
    if ev_date is None:
        return ("TBD", "future")
    if ev_date == today:
        label = "СЕГОДНЯ" if lang == "ru" else "TODAY"
        return (label, "today")
    if ev_date == tomorrow:
        label = "ЗАВТРА" if lang == "ru" else "TOMORROW"
        return (label, "tomorrow")
    wd = ev_date.weekday()
    mo = ev_date.month - 1
    da = ev_date.day
    if lang == "ru":
        label = f"{_WEEKDAYS_RU[wd]} {da:02d} {_MONTHS_RU[mo]}"
    else:
        label = f"{_WEEKDAYS_EN[wd]} {da:02d} {_MONTHS_EN[mo]}"
    return (label, "future")


def _is_live(ev_date: date | None, ev_time: str | None, today: date, now_bkk: datetime) -> bool:
    if ev_date != today or not ev_time:
        return False
    try:
        h, m = map(int, ev_time[:5].split(":"))
        start_h = h + m / 60.0
        now_h = now_bkk.hour + now_bkk.minute / 60.0
        return start_h <= now_h <= start_h + 4
    except Exception:
        return False


def _event_type(category: str | None) -> str:
    if not category:
        return "chill"
    return "chill" if category.lower() in CHILL_CATEGORIES else "party"


def _fomo_hook(price_thb: int | None, filter_score: int | None, lang: str) -> str | None:
    if price_thb is not None and price_thb == 0:
        return "Бесплатно" if lang == "ru" else "Free"
    if filter_score is not None and filter_score > 80:
        return "Высокий спрос" if lang == "ru" else "High demand"
    return None


def _build_event(row: asyncpg.Record, lang: str, today: date, tomorrow: date, now_bkk: datetime) -> dict:
    ev_date = row["event_date"]
    ev_time = row["event_time"]
    category = row["category"] or ""
    price_thb = row["price_thb"]
    filter_score = row.get("filter_score")
    image_path = row["image_path"]

    etype = _event_type(category)
    date_info, date_cat = _date_info(ev_date, lang, today, tomorrow)

    # location resolution
    location = row["location_name"] or row.get("venue_name") or ""

    raw_summary = _resolve_text(row["summary"], lang)

    return {
        "id": str(row["id"]),
        "title": _resolve_text(row["title"], lang),
        "summary": raw_summary[:120] if raw_summary else "",
        "description": _resolve_text(row["description"], lang),
        "location": location,
        "lat": row.get("venue_lat"),
        "lng": row.get("venue_lng"),
        "google_maps_url": row.get("venue_google_maps_url"),
        "dateInfo": date_info,
        "dateCategory": date_cat,
        "timeInfo": ev_time[:5] if ev_time else "TBD",
        "isLive": _is_live(ev_date, ev_time, today, now_bkk),
        "type": etype,
        "category": category,
        "color": TYPE_COLOR.get(etype, "#00f3ff"),
        "fomoHook": _fomo_hook(price_thb, filter_score, lang),
        "price_thb": price_thb if price_thb is not None else 0,
        "imageUrl": f"{MEDIA_BASE}/{image_path}" if image_path else None,
        "source_chat_title": row.get("source_chat_title"),
        "rsvps": (filter_score or 0) * 2 if filter_score else None,
        "facepileUrls": [],
        "distance_km": None,
        "bike_minutes": None,
    }


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get(
    "/events",
    summary="List upcoming events (JWT-protected, frontend contract)",
)
async def list_events(
    lang: Literal["en", "ru"] = Query(default="ru", description="Response language"),
    category: Optional[Literal["party", "chill", "all"]] = Query(default="all"),
    date_filter: Optional[Literal["today", "tomorrow", "all"]] = Query(
        default="all", alias="date"
    ),
    limit: int = Query(default=30, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_lat: Optional[float] = Query(default=None, alias="lat"),
    user_lng: Optional[float] = Query(default=None, alias="lng"),
    pool: asyncpg.Pool = Depends(get_pool),
    _user_id: int = Depends(get_current_user_id),   # enforces Bearer JWT
) -> dict:
    now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
    today = now_bkk.date()
    tomorrow = date.fromordinal(today.toordinal() + 1)

    # ── Build dynamic WHERE ──────────────────────────────────────────────────
    conditions: list[str] = [
        "e.event_date >= (NOW() AT TIME ZONE 'Asia/Bangkok')::date",
        """
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
        """,
        # Hide events the user already swiped (left or right)
        "e.id NOT IN (SELECT event_id FROM user_swipes WHERE user_id = %SWIPE_USER%)"
    ]
    params: list[Any] = []
    idx = 0

    def _p(val: Any) -> str:
        nonlocal idx
        idx += 1
        params.append(val)
        return f"${idx}"

    # Register user_id as the first parameter and replace the placeholder
    swipe_ph = _p(_user_id)
    conditions[-1] = f"e.id NOT IN (SELECT event_id FROM user_swipes WHERE user_id = {swipe_ph})"

    if date_filter == "today":
        conditions.append(f"e.event_date = {_p(today)}")
    elif date_filter == "tomorrow":
        conditions.append(f"e.event_date = {_p(tomorrow)}")

    if category == "party":
        conditions.append(f"e.category = {_p('Party')}")
    elif category == "chill":
        conditions.append(f"e.category = ANY({_p(['Chill', 'Sport', 'Education', 'Business'])}::text[])")

    where = "WHERE " + " AND ".join(conditions)

    limit_ph = _p(limit)
    offset_ph = _p(offset)

    query = f"""
        SELECT
            COUNT(*) OVER()   AS total_count,
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
            v.name            AS venue_name,
            v.lat             AS venue_lat,
            v.lng             AS venue_lng,
            v.google_maps_url AS venue_google_maps_url
        FROM events e
        LEFT JOIN venues v ON e.venue_id = v.id
        {where}
        ORDER BY e.event_date ASC, e.event_time ASC NULLS LAST, e.filter_score DESC NULLS LAST
        LIMIT {limit_ph} OFFSET {offset_ph}
    """

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
    except Exception as exc:
        logger.error("DB error in list_events: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch events",
        )

    total = rows[0]["total_count"] if rows else 0
    events = [_build_event(r, lang, today, tomorrow, now_bkk) for r in rows]

    # Enrich with Mapbox road distances if user sent GPS
    if user_lat is not None and user_lng is not None:
        from app.services.distance_service import enrich_with_distances
        await enrich_with_distances(events, user_lat, user_lng)

    return {
        "events": events,
        "total": total,
        "filters": {
            "lang": lang,
            "date": date_filter or "all",
            "category": category or "all",
        },
    }
