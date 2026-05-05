"""Tests for `shared.media.urls.MediaUrlBuilder`."""

import pytest

from shared.media.urls import MediaUrlBuilder


def test_build_concatenates_base_and_path() -> None:
    b = MediaUrlBuilder(base_url="https://cdn.example.com/api/media")
    assert b.build("avatars/1.jpg") == "https://cdn.example.com/api/media/avatars/1.jpg"


def test_build_strips_leading_slash_from_path() -> None:
    b = MediaUrlBuilder(base_url="https://cdn.example.com/api/media")
    assert b.build("/avatars/1.jpg") == "https://cdn.example.com/api/media/avatars/1.jpg"


def test_build_returns_none_for_empty_path() -> None:
    b = MediaUrlBuilder(base_url="https://cdn.example.com")
    assert b.build(None) is None
    assert b.build("") is None


def test_rejects_empty_base() -> None:
    with pytest.raises(ValueError):
        MediaUrlBuilder(base_url="")


def test_rejects_trailing_slash_base() -> None:
    with pytest.raises(ValueError):
        MediaUrlBuilder(base_url="https://cdn.example.com/")
