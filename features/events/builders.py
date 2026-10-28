"""Pure helpers that build event response dicts.

No DB / framework / IO — just data shaping. Trivial to unit-test.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

import asyncpg

from shared.media.urls import MediaUrlBuilder

# Categories that map to the visual `party` bucket (loud / dance-driven).
# Everything else — yoga, wellness, workshop, sport, market, etc — falls into
# `chill`. Source data lives in the `events.category` column populated by the
# parser; values are lowercase tokens like 'yoga', 'concert', 'sound_healing'.
# Match is case-insensitive (.lower()).
PARTY_CATEGORIES: frozenset[str] = frozenset(
    {"party", "concert", "dance", "ecstatic_dance"}
)

# Backwards-compat alias — kept so external scripts that imported the symbol
# don't break. New code should use PARTY_CATEGORIES.
CHILL_CATEGORIES: frozenset[str] = frozenset()

# Map raw DB category → one of the 6 UI filter buckets used by the frontend.
# Unmapped / unknown categories fall back to "Chill".
UI_CATEGORY_MAP: dict[str, str] = {
    # Sport
    "muay_thai": "Sport",
    "fitness": "Sport",
    "pilates": "Sport",
    "dance": "Sport",
    # Chill
    "yoga": "Chill",
    "wellness": "Chill",
    "breathwork": "Chill",
    "meditation": "Chill",
    "sound_healing": "Chill",
    "circle": "Chill",
    "tantra": "Chill",
    "sound_journey": "Chill",
    "tea": "Chill",
    # Education / Development
    "workshop": "Education",
    "yoga_teacher_training": "Education",
    "women": "Education",
    # Party
    "party": "Party",
    "concert": "Party",
    "ecstatic_dance": "Party",
    # Business / Networking
    "discussion": "Business",
    "event": "Business",
    "market": "Business",
}

TYPE_COLOR: dict[str, str] = {"party": "#ff007f", "chill": "#00f3ff"}

WEEKDAYS_EN = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
WEEKDAYS_RU = ("ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС")
MONTHS_EN = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
             "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
MONTHS_RU = ("ЯНВ", "ФЕВ", "МАР", "АПР", "МАЙ", "ИЮН",
             "ИЮЛ", "АВГ", "СЕН", "ОКТ", "НОЯ", "ДЕК")


def resolve_text(jsonb_val: Any, lang: str) -> str:
    """Extract a localized string from a JSONB column. Falls back ru→en→''. """
    if not jsonb_val:
        return ""
    parsed = jsonb_val
    if isinstance(jsonb_val, str):
        try:
            parsed = json.loads(jsonb_val)
        except Exception:
            return jsonb_val
    if isinstance(parsed, dict):
        return parsed.get(lang) or parsed.get("ru") or parsed.get("en") or ""
    return str(parsed)


def parse_jsonb_dict(raw: Any) -> dict[str, str]:
    """Coerce a JSONB column into a {lang: text} dict.

    Handles three input shapes: dict (passthrough), JSON-encoded string,
    raw plain string (mirrored across both keys).
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"en": raw, "ru": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"en": str(parsed) if parsed else "", "ru": str(parsed) if parsed else ""}
    return {"en": str(raw) if raw else "", "ru": str(raw) if raw else ""}


def parse_jsonb_list(raw: Any) -> list[Any]:
    """Coerce a JSONB array field into a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def row_get(row: asyncpg.Record | dict[str, Any], key: str, default: Any = None) -> Any:
    """Read from asyncpg.Record/dict without assuming every projection has every key."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def date_info(
    ev_date: date | None,
    lang: str,
    today: date,
    tomorrow: date,
) -> tuple[str, str]:
    if ev_date is None:
        return ("TBD", "future")
    if ev_date == today:
        return (("СЕГОДНЯ" if lang == "ru" else "TODAY"), "today")
    if ev_date == tomorrow:
        return (("ЗАВТРА" if lang == "ru" else "TOMORROW"), "tomorrow")
    wd = ev_date.weekday()
    mo = ev_date.month - 1
    da = ev_date.day
    if lang == "ru":
        return (f"{WEEKDAYS_RU[wd]} {da:02d} {MONTHS_RU[mo]}", "future")
    return (f"{WEEKDAYS_EN[wd]} {da:02d} {MONTHS_EN[mo]}", "future")


def is_live(ev_date: date | None, ev_time: str | None, today: date, now_bkk: datetime) -> bool:
    if ev_date != today or not ev_time:
        return False
    try:
        h, m = map(int, ev_time[:5].split(":"))
        start_h = h + m / 60.0
        now_h = now_bkk.hour + now_bkk.minute / 60.0
        return start_h <= now_h <= start_h + 4
    except Exception:
        return False


def event_type(category: str | None) -> str:
    """Map a parser category token to one of the two UI buckets.

    PARTY = explicit allow-list of loud/dance categories.
    CHILL = everything else (default), including empty/unknown.
    """
    if not category:
        return "chill"
    return "party" if category.lower() in PARTY_CATEGORIES else "chill"


def fomo_hook(price_thb: int | None, filter_score: int | None, lang: str) -> str | None:
    if price_thb is not None and price_thb == 0:
        return "Бесплатно" if lang == "ru" else "Free"
    if filter_score is not None and filter_score > 80:
        return "Высокий спрос" if lang == "ru" else "High demand"
    return None


def normalize_event_languages(raw: Any) -> list[str] | None:
    """Return public language codes from the DB array/string, or None when unknown."""
    if raw is None:
        return None
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        return None

    normalized: list[str] = []
    for value in values:
        code = str(value).strip().lower()
        if code in {"en", "eng", "english"}:
            public = "EN"
        elif code in {"ru", "rus", "russian", "русский"}:
            public = "RU"
        else:
            continue
        if public not in normalized:
            normalized.append(public)
    return normalized or None


def _time_to_minutes(value: Any) -> int | None:
    if value is None:
        return None
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return int(value.hour) * 60 + int(value.minute)
    text = str(value).strip()
    if not text:
        return None
    try:
        hours, minutes = map(int, text[:5].split(":"))
    except (TypeError, ValueError):
        return None
    return hours * 60 + minutes


def _duration_to_minutes(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None

    compact = re.fullmatch(r"(\d+)\s*h\s*(\d+)", text)
    if compact:
        return int(compact.group(1)) * 60 + int(compact.group(2))

    total = 0.0
    seen = False
    for value, unit in re.findall(
        r"(\d+(?:[.,]\d+)?)\s*(hours?|hrs?|h|ч|minutes?|mins?|min|m|мин)",
        text,
    ):
        seen = True
        amount = float(value.replace(",", "."))
        if unit.startswith(("h", "ч")):
            total += amount * 60
        else:
            total += amount

    if seen:
        return max(1, round(total))
    if text.isdigit():
        return int(text)
    return None


_DAYS_RE = re.compile(r"(\d+)\s*(?:days?|дн[яей]|день)")


def _format_days(days: int, lang: str) -> str:
    if lang == "ru":
        if days % 10 == 1 and days % 100 != 11:
            return f"{days} день"
        if 2 <= days % 10 <= 4 and not 12 <= days % 100 <= 14:
            return f"{days} дня"
        return f"{days} дней"
    return f"{days} day" if days == 1 else f"{days} days"


def _format_duration_minutes(minutes: int | None, lang: str) -> str | None:
    if minutes is None or minutes <= 0:
        return None
    hours, mins = divmod(minutes, 60)
    if lang == "ru":
        parts = []
        if hours:
            parts.append(f"{hours} ч")
        if mins:
            parts.append(f"{mins} мин")
        return " ".join(parts)
    parts = []
    if hours:
        parts.append(f"{hours} h")
    if mins:
        parts.append(f"{mins} min")
    return " ".join(parts)


def duration_info(
    raw_duration: Any,
    start_time: Any,
    end_time: Any,
    *,
    ends_next_day: bool,
    lang: str,
) -> str | None:
    days = _DAYS_RE.search(str(raw_duration or "").lower())
    if days and int(days.group(1)) > 1:
        return _format_days(int(days.group(1)), lang)
    minutes = _duration_to_minutes(raw_duration)
    if minutes is None:
        start_minutes = _time_to_minutes(start_time)
        end_minutes = _time_to_minutes(end_time)
        if start_minutes is not None and end_minutes is not None:
            if ends_next_day or end_minutes < start_minutes:
                end_minutes += 24 * 60
            minutes = end_minutes - start_minutes
    return _format_duration_minutes(minutes, lang)


def time_range_info(start_time: Any, end_time: Any, fallback: str) -> str:
    start = str(start_time or "").strip()
    end = str(end_time or "").strip()
    if start and end:
        return f"{start[:5]}–{end[:5]}"
    return fallback


def build_event(
    row: asyncpg.Record,
    *,
    lang: str,
    today: date,
    tomorrow: date,
    now_bkk: datetime,
    media_base_url: str,
) -> dict[str, Any]:
    """Build the public event dict that the frontend expects."""
    ev_date = row_get(row, "event_date")
    ev_time = row_get(row, "event_time")
    start_time = row_get(row, "start_time") or (ev_time[:5] if ev_time else "")
    end_time = row_get(row, "end_time")
    category = row_get(row, "category") or ""
    price_thb = row_get(row, "price_thb")
    filter_score = row_get(row, "filter_score")
    image_path = row_get(row, "image_path")
    media_builder = MediaUrlBuilder(media_base_url)
    media = []
    for item in parse_jsonb_list(row_get(row, "media")):
        if not isinstance(item, dict):
            continue
        storage_key = item.get("storage_key")
        media.append(
            {
                "id": item.get("id"),
                "type": item.get("type") or item.get("media_type") or "image",
                "storage_key": storage_key,
                "url": media_builder.build(storage_key),
                "source_url": item.get("source_url"),
                "sort_order": item.get("sort_order", 0),
                "is_cover": bool(item.get("is_cover")),
                "metadata": item.get("metadata") or {},
            }
        )

    etype = event_type(category)
    ui_cat = UI_CATEGORY_MAP.get(category.lower(), "Chill") if category else "Chill"
    di_label, di_cat = date_info(ev_date, lang, today, tomorrow)
    location = row_get(row, "location_name") or row_get(row, "venue_name") or ""
    raw_summary = resolve_text(row_get(row, "summary"), lang)
    venue_name = (
        row_get(row, "venue_name_ru")
        if lang == "ru" and row_get(row, "venue_name_ru")
        else row_get(row, "venue_name")
    )
    venue_id = row_get(row, "venue_id")
    venue = None
    if venue_id is not None or venue_name:
        venue = {
            "id": venue_id,
            "name": venue_name or location,
            "rating": row_get(row, "venue_rating"),
            "reviews_count": row_get(row, "venue_reviews_count"),
            "events_count": row_get(row, "venue_events_count"),
        }
    # Only all-day events (retreats, festivals, multi-day) are published without a start time.
    time_info = ev_time[:5] if ev_time else ("Весь день" if lang == "ru" else "All day")
    duration_label = duration_info(
        row_get(row, "duration"),
        start_time,
        end_time,
        ends_next_day=bool(row_get(row, "ends_next_day")),
        lang=lang,
    )

    return {
        "id": str(row_get(row, "id")),
        "public_id": str(row_get(row, "public_id")) if row_get(row, "public_id") else None,
        "slug": row_get(row, "slug"),
        "event_date": ev_date.isoformat() if ev_date else None,
        "title": resolve_text(row_get(row, "title"), lang),
        "summary": raw_summary[:120] if raw_summary else "",
        "description": resolve_text(row_get(row, "description"), lang),
        "sharing_description": resolve_text(row_get(row, "sharing_description"), lang),
        "requirements": resolve_text(row_get(row, "requirements"), lang),
        "keywords": parse_jsonb_dict(row_get(row, "keywords")),
        "demographic_filters": parse_jsonb_dict(row_get(row, "demographic_filters")),
        "ai_addons": parse_jsonb_list(row_get(row, "ai_addons")),
        "capacity": row_get(row, "capacity"),
        "metadata_status": row_get(row, "metadata_status"),
        "public_status": row_get(row, "public_status"),
        "timezone": row_get(row, "timezone") or "Asia/Bangkok",
        "event_type": row_get(row, "event_type"),
        "event_category": row_get(row, "event_category"),
        "event_sub_category": row_get(row, "event_sub_category"),
        "location": location,
        "lat": row_get(row, "venue_lat"),
        "lng": row_get(row, "venue_lng"),
        "google_maps_url": row_get(row, "venue_google_maps_url"),
        "venue": venue,
        "dateInfo": di_label,
        "dateCategory": di_cat,
        "event_time": ev_time[:5] if ev_time else "",
        "start_time": start_time,
        "end_time": end_time,
        "ends_next_day": bool(row_get(row, "ends_next_day")),
        "timeInfo": time_info,
        "timeRangeInfo": time_range_info(start_time, end_time, time_info),
        "durationInfo": duration_label,
        "event_languages": normalize_event_languages(row_get(row, "event_languages")),
        "isLive": is_live(ev_date, ev_time, today, now_bkk),
        "type": etype,
        "category": category,
        "ui_category": ui_cat,
        "color": TYPE_COLOR.get(etype, "#00f3ff"),
        "fomoHook": fomo_hook(price_thb, filter_score, lang),
        "recurrence_type": row_get(row, "recurrence_type"),
        "price_thb": price_thb if price_thb is not None else 0,
        "currency_code": row_get(row, "currency_code") or "THB",
        "media": media,
        "faqs": parse_jsonb_list(row_get(row, "faqs")),
        "imageUrl": media_builder.build(image_path),
        "source_chat_title": row_get(row, "source_chat_title"),
        "sender_id": str(row_get(row, "sender_id")) if row_get(row, "sender_id") else None,
        "rsvps": (filter_score or 0) * 2 if filter_score else None,
        "attendeeCount": 0,
        "facepileUrls": [],
        "distance_km": None,
        "bike_minutes": None,
    }
