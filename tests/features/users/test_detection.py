"""Unit tests for gender + language detection (no DB / network)."""

from __future__ import annotations

from features.users.gender_detection import (
    guess_by_morphology,
    has_letters,
    lookup_dictionary,
)
from features.users.language_detection import (
    detect_language_sync,
    name_in_ru_dict,
)


def test_dictionary_female_ru() -> None:
    assert lookup_dictionary("Анна") == "female"
    assert lookup_dictionary("анастасия") == "female"


def test_dictionary_male_ru() -> None:
    assert lookup_dictionary("Александр") == "male"
    assert lookup_dictionary("Дима") == "male"


def test_dictionary_unknown() -> None:
    assert lookup_dictionary("Зурван") is None


def test_has_letters() -> None:
    assert has_letters("Anna") is True
    assert has_letters("Анна") is True
    assert has_letters("🦁🦊") is False
    assert has_letters("123") is False


def test_morphology_female_ending() -> None:
    assert guess_by_morphology("Зурвана") == "female"
    assert guess_by_morphology("Кристина") == "female"


def test_morphology_male_ending() -> None:
    assert guess_by_morphology("Зурван") == "male"


def test_morphology_returns_none_for_latin() -> None:
    assert guess_by_morphology("Anna") is None


def test_detect_language_sync_cyrillic() -> None:
    assert detect_language_sync("Анна", "en-US") == "ru"


def test_detect_language_sync_lang_code_ru() -> None:
    assert detect_language_sync("Anna", "ru") == "ru"


def test_detect_language_sync_default_en() -> None:
    assert detect_language_sync("John", "en-US") == "en"


def test_detect_language_sync_ru_dict_latin() -> None:
    assert detect_language_sync("Polina", "en") == "ru"


def test_name_in_ru_dict() -> None:
    assert name_in_ru_dict("Анна")
    assert name_in_ru_dict("Polina")
    assert not name_in_ru_dict("John")
