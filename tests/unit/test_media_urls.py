"""Tests for `shared.media.urls.MediaUrlBuilder`."""

import pytest

from shared.media.urls import MediaUrlBuilder


def test_build_concatenates_base_and_path() -> None:
    b = MediaUrlBuilder(base_url="https://cdn.example.com/api/media")
    assert b.build("avatars/1.jpg") == "https://cdn.example.com/api/media/avatars/1.jpg"


def test_build_encodes_but_preserves_path_separators() -> None:
    b = MediaUrlBuilder(base_url="https://cdn.example.com/api/media")
    assert b.build("events/tlg poster.webp") == "https://cdn.example.com/api/media/events/tlg%20poster.webp"


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


@pytest.mark.parametrize("path", ["/avatars/1.jpg", "../x.jpg", "avatars/../x.jpg"])
def test_rejects_unsafe_paths(path: str) -> None:
    b = MediaUrlBuilder(base_url="https://cdn.example.com/api/media")
    with pytest.raises(ValueError):
        b.build(path)
