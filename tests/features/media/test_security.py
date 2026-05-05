"""Unit tests for media path security."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import AuthorizationError, ValidationError
from features.media.security import resolve_safe_media_path


def test_resolves_valid_path(tmp_path: Path) -> None:
    base = tmp_path / "media"
    base.mkdir()
    (base / "image.webp").write_bytes(b"x")
    resolved = resolve_safe_media_path("image.webp", base_dir=base)
    assert resolved.absolute == (base / "image.webp").resolve()


def test_rejects_traversal(tmp_path: Path) -> None:
    base = tmp_path / "media"
    base.mkdir()
    with pytest.raises((ValidationError, AuthorizationError)):
        resolve_safe_media_path("../../etc/passwd", base_dir=base)


def test_rejects_absolute_path(tmp_path: Path) -> None:
    base = tmp_path / "media"
    base.mkdir()
    with pytest.raises((ValidationError, AuthorizationError)):
        resolve_safe_media_path("/etc/passwd", base_dir=base)
