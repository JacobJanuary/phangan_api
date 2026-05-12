"""Pure media path validation + safe filesystem resolution.

No I/O for validation — only path computation. The actual filesystem
checks (`is_file`) live in the service layer so this module remains
unit-testable without mocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.exceptions import AuthorizationError, ValidationError

# Strict pattern: alphanumeric + underscore + dash, optional safe subdirectory,
# image extension only. Rejects any '..' / leading slash / dot segments.
_FILEPATH_PATTERN = re.compile(
    r"^[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*\.(jpg|jpeg|png|webp)$"
)

CONTENT_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@dataclass(frozen=True, slots=True)
class ResolvedMediaPath:
    """A validated absolute path inside the configured media root."""

    absolute: Path
    content_type: str


def resolve_safe_media_path(file_path: str, base_dir: Path) -> ResolvedMediaPath:
    """Validate `file_path` and resolve it to an absolute path inside `base_dir`.

    Raises:
        ValidationError: format does not match the strict pattern.
        AuthorizationError: resolved path escapes the configured base.
    """
    if not _FILEPATH_PATTERN.match(file_path):
        raise ValidationError(
            "Invalid media path format",
            details={"path": file_path},
        )

    base = base_dir.resolve()
    resolved = (base / file_path).resolve()

    # Use the modern `is_relative_to` for robust traversal protection.
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise AuthorizationError(
            "Path traversal attempt rejected",
            details={"path": file_path},
        ) from exc

    suffix = resolved.suffix.lower()
    return ResolvedMediaPath(
        absolute=resolved,
        content_type=CONTENT_TYPES.get(suffix, "application/octet-stream"),
    )
