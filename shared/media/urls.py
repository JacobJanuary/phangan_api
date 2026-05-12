"""Build absolute media URLs from relative storage paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote


def safe_relative_media_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = str(path).strip().replace("\\", "/")
    if not cleaned:
        return None
    posix = PurePosixPath(cleaned)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"Unsafe media path: {path!r}")
    return "/".join(posix.parts)


@dataclass(frozen=True, slots=True)
class MediaUrlBuilder:
    """Compose absolute media URLs from a configured base.

    The base must NOT end with a slash; the helper strips a single
    leading slash from `path` to keep the result canonical.
    """

    base_url: str

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("MediaUrlBuilder.base_url must be a non-empty string")
        if self.base_url.endswith("/"):
            # Frozen dataclass — cannot mutate; fail loudly to prevent silent bugs.
            raise ValueError("MediaUrlBuilder.base_url must not end with '/'")

    def build(self, path: str | None) -> str | None:
        """Return absolute URL for `path`, or None if `path` is empty."""
        safe_path = safe_relative_media_path(path)
        if not safe_path:
            return None
        return f"{self.base_url}/{quote(safe_path, safe='/')}"
