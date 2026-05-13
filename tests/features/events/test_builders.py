"""Unit tests for `features.events.builders` — pure functions, no IO."""

from __future__ import annotations

from datetime import date, datetime

from features.events.builders import (
    build_event,
    date_info,
    event_type,
    fomo_hook,
    is_live,
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


def test_build_event_uses_safe_media_builder() -> None:
    row = {
        "id": 1,
        "public_id": "7ff6d57f-8a4f-4c25-9c05-2fb7c5d17a21",
        "slug": "yoga-1",
        "event_date": date(2025, 1, 15),
        "title": {"en": "Yoga", "ru": "Йога"},
        "summary": {"en": "Short", "ru": "Коротко"},
        "description": {"en": "Desc", "ru": "Описание"},
        "sharing_description": {"en": "Share", "ru": "Шер"},
        "requirements": {"en": "Bring water", "ru": "Вода"},
        "keywords": {"en": ["yoga"], "ru": ["йога"]},
        "demographic_filters": {"is18Plus": False, "menOnly": False, "womenOnly": False, "noKids": False},
        "ai_addons": ["bring_reminder"],
        "capacity": 20,
        "metadata_status": "complete",
        "public_status": "published",
        "timezone": "Asia/Bangkok",
        "event_type": "classTrainingOrWorkshop",
        "event_category": "healthAndWellness",
        "event_sub_category": "yoga",
        "location_name": "Studio",
        "venue_name": "Studio",
        "venue_lat": 9.7,
        "venue_lng": 100.0,
        "venue_google_maps_url": "https://maps.example/venue",
        "event_time": "18:00",
        "start_time": "18:00",
        "end_time": None,
        "ends_next_day": False,
        "category": "yoga",
        "price_thb": 0,
        "currency_code": "THB",
        "filter_score": 3,
        "recurrence_type": None,
        "image_path": "events/tlg poster.webp",
        "media": [
            {
                "id": 1,
                "type": "image",
                "storage_key": "events/tlg poster.webp",
                "sort_order": 0,
                "is_cover": True,
                "metadata": {},
            }
        ],
        "faqs": [{"question": {"en": "What?"}, "answer": {"en": "Water."}}],
        "source_chat_title": "Chat",
        "sender_id": 123,
    }

    out = build_event(
        row,
        lang="en",
        today=date(2025, 1, 15),
        tomorrow=date(2025, 1, 16),
        now_bkk=datetime(2025, 1, 15, 12, 0),
        media_base_url="https://cdn.example.com/api/media/",
    )

    assert out["google_maps_url"] == "https://maps.example/venue"
    assert out["imageUrl"] == "https://cdn.example.com/api/media/events/tlg%20poster.webp"
    assert out["public_id"] == "7ff6d57f-8a4f-4c25-9c05-2fb7c5d17a21"
    assert out["slug"] == "yoga-1"
    assert out["sharing_description"] == "Share"
    assert out["keywords"]["en"] == ["yoga"]
    assert out["media"][0]["url"] == "https://cdn.example.com/api/media/events/tlg%20poster.webp"
    assert out["faqs"][0]["answer"]["en"] == "Water."
