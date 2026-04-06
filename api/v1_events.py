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
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.db.database import get_pool
from app.schemas.events import EventUpdate

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
        "event_date": ev_date.isoformat() if ev_date else None,
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
        "recurrence_type": row.get("recurrence_type"),
        "price_thb": price_thb if price_thb is not None else 0,
        "imageUrl": f"{MEDIA_BASE}/{image_path}" if image_path else None,
        "source_chat_title": row.get("source_chat_title"),
        "sender_id": str(row["sender_id"]) if row.get("sender_id") else None,
        "rsvps": (filter_score or 0) * 2 if filter_score else None,
        "attendeeCount": 0,
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
            e.sender_id,
            e.recurrence_type,
            v.name            AS venue_name,
            v.lat             AS venue_lat,
            v.lng             AS venue_lng,
            COALESCE(e.google_maps_url, v.google_maps_url) AS venue_google_maps_url
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

    # Enrich with facepile avatars ("Кто пойдёт?")
    if events:
        from app.services.facepile_service import get_facepile_batch

        # Get viewer gender for gender-targeted phantom selection
        viewer_gender = None
        try:
            async with pool.acquire() as conn:
                viewer_gender = await conn.fetchval(
                    "SELECT gender FROM users WHERE id = $1", _user_id
                )
        except Exception:
            pass

        event_ids = [int(ev["id"]) for ev in events]
        event_categories = {int(ev["id"]): ev.get("category", "") for ev in events}

        try:
            facepile_data = await get_facepile_batch(
                event_ids, event_categories, viewer_gender, pool
            )
            for ev in events:
                fp = facepile_data.get(int(ev["id"]))
                if fp:
                    ev["attendeeCount"] = fp["count"]
                    ev["facepileUrls"] = fp["avatarUrls"]
        except Exception as exc:
            logger.warning("Facepile enrichment failed: %s", exc)

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


@router.get("/events/{event_id}", summary="Get a single event by ID")
async def get_event(
    event_id: int,
    lang: Literal["en", "ru"] = Query(default="ru", description="Response language"),
    pool: asyncpg.Pool = Depends(get_pool),
    _user_id: int = Depends(get_current_user_id),
):
    now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
    today = now_bkk.date()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    
    query = """
        SELECT
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
            v.name            AS venue_name,
            v.lat             AS venue_lat,
            v.lng             AS venue_lng,
            COALESCE(e.google_maps_url, v.google_maps_url) AS venue_google_maps_url
        FROM events e
        LEFT JOIN venues v ON e.venue_id = v.id
        WHERE e.id = $1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, event_id)
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        
        event_dict = _build_event(row, lang, today, tomorrow, now_bkk)
        
        # Include raw JSONB dicts so the edit form can populate both language inputs
        import json as _json
        for jsonb_field in ("title", "summary", "description"):
            raw = row[jsonb_field]
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except (_json.JSONDecodeError, TypeError):
                    raw = {"en": raw, "ru": raw}
            if not isinstance(raw, dict):
                raw = {"en": str(raw) if raw else "", "ru": str(raw) if raw else ""}
            event_dict[f"{jsonb_field}_raw"] = raw

        from app.services.facepile_service import get_facepile_batch
        viewer_gender = await conn.fetchval("SELECT gender FROM users WHERE id = $1", _user_id)
        try:
            fp_data = await get_facepile_batch([event_id], {event_id: event_dict.get("category", "")}, viewer_gender, pool)
            fp = fp_data.get(event_id)
            if fp:
                event_dict["attendeeCount"] = fp["count"]
                event_dict["facepileUrls"] = fp["avatarUrls"]
        except Exception:
            pass
            
        return event_dict


@router.put("/events/{event_id}", summary="Update an event (Only Author)")
async def update_event(
    event_id: int,
    payload: EventUpdate,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Updates an event's title, summary, description, category, date, time, location, or price.
    Only the original author (matching sender_id) can perform this action.
    """
    async with pool.acquire() as conn:
        # 1. Resolve caller's telegram_id (JWT sub = internal users.id, but sender_id = telegram_id)
        caller_tg_id = await conn.fetchval(
            "SELECT telegram_id FROM users WHERE id = $1", current_user_id
        )

        # 2. Verify existence and ownership
        row = await conn.fetchrow("SELECT sender_id FROM events WHERE id = $1", event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        if row["sender_id"] != caller_tg_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to edit this event"
            )

        # 2. Build dynamic update query
        update_fields = []
        params = []
        idx = 1

        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                if field in ("title", "summary", "description"):
                    import json
                    # MERGE with existing JSONB using || to preserve other-language keys
                    # e.g. sending {"ru": "Новое"} won't erase the existing "en" key
                    update_fields.append(f"{field} = COALESCE({field}, '{{}}') || ${idx}::jsonb")
                    params.append(json.dumps(value, ensure_ascii=False))
                elif field == "event_date":
                    from datetime import date as _date
                    update_fields.append(f"{field} = ${idx}")
                    params.append(_date.fromisoformat(value))
                else:
                    update_fields.append(f"{field} = ${idx}")
                    params.append(value)
                idx += 1

        if not update_fields:
            return {"status": "ok", "message": "No fields to update"}

        params.append(event_id)
        query = f"""
            UPDATE events
            SET {', '.join(update_fields)}
            WHERE id = ${idx}
        """

        await conn.execute(query, *params)
        return {"status": "ok", "message": "Event updated successfully"}


@router.delete("/events/{event_id}", summary="Delete an event (Only Author)")
async def delete_event(
    event_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Deletes an event from the database. Only the original author can perform this action.
    """
    async with pool.acquire() as conn:
        caller_tg_id = await conn.fetchval(
            "SELECT telegram_id FROM users WHERE id = $1", current_user_id
        )

        row = await conn.fetchrow("SELECT sender_id FROM events WHERE id = $1", event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        if row["sender_id"] != caller_tg_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this event"
            )

        # Clean up FK references BEFORE deleting parent event row
        await conn.execute("DELETE FROM user_swipes WHERE event_id = $1", event_id)
        await conn.execute("DELETE FROM outreach_log WHERE event_id = $1", event_id)

        await conn.execute("DELETE FROM events WHERE id = $1", event_id)

        return {"status": "ok", "message": "Event deleted successfully"}


@router.post(
    "/events/{event_id}/image",
    summary="Upload / replace event cover image (Only Author)",
    status_code=status.HTTP_200_OK,
)
async def upload_event_image(
    event_id: int,
    file: UploadFile = File(...),
    pool: asyncpg.Pool = Depends(get_pool),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Upload or replace an event's cover image.
    Pipeline (mirrors TG_parcer):
      1. Validate MIME type (JPEG, PNG, WebP only)
      2. Read up to 5 MB
      3. Convert to RGB
      4. Resize to max 600px width (LANCZOS)
      5. Save as WebP (quality=85, method=6)
      6. Update events.image_path in DB
    Only the original author (sender_id) can upload.
    """
    # ── 1. Validate MIME ─────────────────────────────────────────────────
    ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{file.content_type}'. Allowed: JPEG, PNG, WebP.",
        )

    # ── 2. Read & size check (5 MB max) ──────────────────────────────────
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB.",
        )

    async with pool.acquire() as conn:
        # ── 3. Resolve telegram_id & verify existence + ownership ────────
        caller_tg_id = await conn.fetchval(
            "SELECT telegram_id FROM users WHERE id = $1", current_user_id
        )

        row = await conn.fetchrow(
            "SELECT sender_id, category, image_path FROM events WHERE id = $1",
            event_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if row["sender_id"] != caller_tg_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to edit this event",
            )

        # ── 4. Process image (same as TG_parcer) ────────────────────────
        import os
        from io import BytesIO
        from pathlib import Path
        from PIL import Image

        image = Image.open(BytesIO(content))
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize to max 600px width for mobile (Retina-ready)
        target_width = 600
        w, h = image.size
        if w > target_width:
            target_height = int(h * (target_width / w))
            resample_filter = getattr(Image, "Resampling", Image).LANCZOS
            image = image.resize((target_width, target_height), resample_filter)

        # Save as WebP
        category = (row["category"] or "other").lower()
        filename = f"event_{category}_{os.urandom(4).hex()}.webp"
        settings = get_settings()
        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        filepath = media_dir / filename

        image.save(str(filepath), "WEBP", quality=85, method=6)
        logger.info("📸 Event %d: saved image %s (%dx%d)", event_id, filename, image.width, image.height)

        # ── 5. Delete old image file if it exists ────────────────────────
        old_path = row["image_path"]
        if old_path:
            old_file = media_dir / old_path
            if old_file.is_file():
                try:
                    old_file.unlink()
                    logger.info("🗑️ Deleted old image: %s", old_path)
                except OSError:
                    pass

        # ── 6. Update DB ─────────────────────────────────────────────────
        await conn.execute(
            "UPDATE events SET image_path = $1 WHERE id = $2",
            filename, event_id,
        )

    return {
        "status": "ok",
        "message": "Image uploaded successfully",
        "imageUrl": f"{MEDIA_BASE}/{filename}",
    }
