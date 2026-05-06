"""Unit tests for `features.events.builders` — pure functions, no IO."""

from __future__ import annotations

from datetime import date, datetime

from features.events.builders import (
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
