"""Pure helpers that build event response dicts.

No DB / framework / IO — just data shaping. Trivial to unit-test.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import asyncpg

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
    ev_date = row["event_date"]
    ev_time = row["event_time"]
    category = row["category"] or ""
    price_thb = row["price_thb"]
    filter_score = row["filter_score"] if "filter_score" in row else None
    image_path = row["image_path"]

    etype = event_type(category)
    di_label, di_cat = date_info(ev_date, lang, today, tomorrow)
    location = row["location_name"] or row["venue_name"] or ""
    raw_summary = resolve_text(row["summary"], lang)

    return {
        "id": str(row["id"]),
        "event_date": ev_date.isoformat() if ev_date else None,
        "title": resolve_text(row["title"], lang),
        "summary": raw_summary[:120] if raw_summary else "",
        "description": resolve_text(row["description"], lang),
        "location": location,
        "lat": row["venue_lat"],
        "lng": row["venue_lng"],
        "google_maps_url": row["venue_google_maps_url"],
        "dateInfo": di_label,
        "dateCategory": di_cat,
        "event_time": ev_time[:5] if ev_time else "",
        "timeInfo": ev_time[:5] if ev_time else "TBD",
        "isLive": is_live(ev_date, ev_time, today, now_bkk),
        "type": etype,
        "category": category,
        "color": TYPE_COLOR.get(etype, "#00f3ff"),
        "fomoHook": fomo_hook(price_thb, filter_score, lang),
        "recurrence_type": row["recurrence_type"],
        "price_thb": price_thb if price_thb is not None else 0,
        "imageUrl": f"{media_base_url}/{image_path}" if image_path else None,
        "source_chat_title": row["source_chat_title"],
        "sender_id": str(row["sender_id"]) if row["sender_id"] else None,
        "rsvps": (filter_score or 0) * 2 if filter_score else None,
        "attendeeCount": 0,
        "facepileUrls": [],
        "distance_km": None,
        "bike_minutes": None,
    }
