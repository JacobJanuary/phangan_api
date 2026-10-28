"""Unit tests for `features.events.builders` — pure functions, no IO."""

from __future__ import annotations

from datetime import date, datetime

from features.events.builders import (
    build_event,
    date_info,
    duration_info,
    event_type,
    fomo_hook,
    is_live,
    normalize_event_languages,
    parse_jsonb_dict,
    resolve_text,
)


def test_resolve_text_dict() -> None:
    assert resolve_text({"ru": "Привет", "en": "Hi"}, "ru") == "Привет"
    assert resolve_text({"ru": "Привет", "en": "Hi"}, "en") == "Hi"


def test_resolve_text_falls_back_to_ru_then_en() -> None:
    assert resolve_text({"en": "Hi"}, "fr") == "Hi"
    assert resolve_text({"ru": "Привет"}, "fr") == "Привет"


def test_resolve_text_string_json() -> None:
    assert resolve_text('{"en": "x"}', "en") == "x"


def test_resolve_text_plain_string() -> None:
    assert resolve_text("plain", "en") == "plain"


def test_resolve_text_empty() -> None:
    assert resolve_text(None, "en") == ""
    assert resolve_text("", "en") == ""


def test_parse_jsonb_dict_passthrough() -> None:
    assert parse_jsonb_dict({"en": "a"}) == {"en": "a"}


def test_parse_jsonb_dict_plain_string_mirrored() -> None:
    out = parse_jsonb_dict("hello")
    assert out == {"en": "hello", "ru": "hello"}


def test_event_type_chill_buckets() -> None:
    # PARTY = explicit allow-list (case-insensitive).
    assert event_type("party") == "party"
    assert event_type("Party") == "party"
    assert event_type("concert") == "party"
    assert event_type("dance") == "party"
    assert event_type("ecstatic_dance") == "party"
    # Everything else collapses into chill.
    assert event_type("yoga") == "chill"
    assert event_type("workshop") == "chill"
    assert event_type("muay_thai") == "chill"
    assert event_type("sound_healing") == "chill"
    assert event_type("Chill") == "chill"
    assert event_type(None) == "chill"
    assert event_type("") == "chill"


def test_date_info_today_tomorrow() -> None:
    today = date(2025, 1, 15)
    tomorrow = date(2025, 1, 16)
    assert date_info(today, "ru", today, tomorrow) == ("СЕГОДНЯ", "today")
    assert date_info(tomorrow, "en", today, tomorrow) == ("TOMORROW", "tomorrow")
    label, cat = date_info(date(2025, 1, 20), "en", today, tomorrow)
    assert cat == "future"
    assert "MON" in label  # 2025-01-20 is Monday


def test_is_live_within_window() -> None:
    today = date(2025, 1, 15)
    now = datetime(2025, 1, 15, 21, 30)
    assert is_live(today, "20:00", today, now) is True
    assert is_live(today, "23:30", today, now) is False  # not yet started
    assert is_live(today, "16:00", today, now) is False  # >4h ago


def test_fomo_hook_free() -> None:
    assert fomo_hook(0, None, "ru") == "Бесплатно"
    assert fomo_hook(0, None, "en") == "Free"


def test_fomo_hook_high_demand() -> None:
    assert fomo_hook(100, 90, "en") == "High demand"
    assert fomo_hook(100, 50, "en") is None


def test_duration_info_prefers_duration_then_falls_back_to_time_range() -> None:
    assert duration_info("1h30", "18:00", "19:00", ends_next_day=False, lang="ru") == "1 ч 30 мин"
    assert duration_info(None, "23:30", "01:00", ends_next_day=True, lang="en") == "1 h 30 min"


def test_normalize_event_languages_returns_public_codes() -> None:
    assert normalize_event_languages(["en", "russian", "th"]) == ["EN", "RU"]
    assert normalize_event_languages(None) is None


def test_build_event_uses_typed_time_and_media_table_contract() -> None:
    row = {
        "id": 42,
        "public_id": "7ff6d57f-8a4f-4c25-9c05-2fb7c5d17a21",
        "slug": "sample-event-42",
        "event_date": date(2026, 5, 14),
        "event_time": "18:30",
        "start_time": "18:30",
        "end_time": "20:00",
        "ends_next_day": False,
        "duration": "1h30",
        "event_languages": ["en", "ru"],
        "title": {"en": "Sample Event", "ru": "Событие"},
        "summary": {"en": "Short summary", "ru": "Коротко"},
        "description": {"en": "Full description", "ru": "Описание"},
        "sharing_description": {"en": "Share me", "ru": "Поделиться"},
        "requirements": {"en": "Bring water", "ru": "Вода"},
        "keywords": {"en": ["music"], "ru": ["музыка"]},
        "demographic_filters": {"is18Plus": True, "menOnly": False, "womenOnly": False, "noKids": False},
        "ai_addons": ["bring_reminder"],
        "capacity": 30,
        "metadata_status": "complete",
        "public_status": "published",
        "timezone": "Asia/Bangkok",
        "event_type": "classTrainingOrWorkshop",
        "event_category": "music",
        "event_sub_category": "instrumental-lesson",
        "category": "workshop",
        "location_name": "Secret Location",
        "venue_id": 100,
        "venue_name": "Venue EN",
        "venue_name_ru": "Площадка RU",
        "venue_lat": None,
        "venue_lng": None,
        "venue_google_maps_url": "https://maps.example/venue",
        "venue_rating": 4.9,
        "venue_reviews_count": 34,
        "venue_events_count": 12,
        "price_thb": 0,
        "currency_code": "THB",
        "filter_score": 77,
        "image_path": "events/sample.webp",
        "media": [
            {
                "id": 1,
                "type": "image",
                "storage_key": "events/sample.webp",
                "sort_order": 0,
                "is_cover": True,
                "metadata": {},
            }
        ],
        "faqs": [
            {
                "id": 1,
                "question": {"en": "What to bring?"},
                "answer": {"en": "Water."},
                "sort_order": 0,
            }
        ],
        "source_chat_title": "chat",
        "sender_id": 123,
        "recurrence_type": None,
    }

    event = build_event(
        row,
        lang="en",
        today=date(2026, 5, 13),
        tomorrow=date(2026, 5, 14),
        now_bkk=datetime(2026, 5, 13, 12, 0),
        media_base_url="https://api.example/media",
    )

    assert event["event_time"] == "18:30"
    assert event["start_time"] == "18:30"
    assert event["timeRangeInfo"] == "18:30–20:00"
    assert event["durationInfo"] == "1 h 30 min"
    assert event["event_languages"] == ["EN", "RU"]
    assert event["venue"] == {
        "id": 100,
        "name": "Venue EN",
        "rating": 4.9,
        "reviews_count": 34,
        "events_count": 12,
    }
    assert event["imageUrl"] == "https://api.example/media/events/sample.webp"
    assert event["media"][0]["url"] == "https://api.example/media/events/sample.webp"
    assert event["google_maps_url"] == "https://maps.example/venue"
    assert event["sharing_description"] == "Share me"
    assert event["keywords"]["en"] == ["music"]
    assert event["faqs"][0]["answer"]["en"] == "Water."

