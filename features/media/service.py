"""Media use cases: serve files, accept story uploads."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from core.config import Settings
from core.exceptions import NotFoundError, ValidationError
from features.media.security import ResolvedMediaPath, resolve_safe_media_path

logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_ALLOWED_UPLOAD_MIMES = {"image/png", "image/jpeg", "image/webp"}
_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


@dataclass(slots=True)
class MediaService:
    """Filesystem-backed media operations."""

    settings: Settings

    @property
    def _media_root(self) -> Path:
        return Path(self.settings.MEDIA_DIR)

    @property
    def _stories_dir(self) -> Path:
        return self._media_root / "stories"

    def resolve_for_serving(self, file_path: str) -> ResolvedMediaPath:
        """Validate the request and ensure the file actually exists."""
        resolved = resolve_safe_media_path(file_path, self._media_root)
        if not resolved.absolute.is_file():
            raise NotFoundError(
                "Media file not found",
                details={"path": file_path},
            )
        return resolved

    async def save_story(
        self, *, content: bytes, content_type: str | None, original_filename: str | None
    ) -> str:
        """Persist a generated story image and return its public URL."""
        if content_type not in _ALLOWED_UPLOAD_MIMES:
            raise ValidationError(
                "Forbidden format. Only PNG, JPEG, and WebP are allowed.",
                details={"content_type": content_type},
            )
        if len(content) > _MAX_UPLOAD_BYTES:
            raise ValidationError("File too large. Maximum size is 5MB.")

        ext = "png"
        if original_filename and "." in original_filename:
            candidate = original_filename.rsplit(".", 1)[1].lower()
            if candidate in _ALLOWED_EXTENSIONS:
                ext = candidate

        self._stories_dir.mkdir(parents=True, exist_ok=True)
        filename = f"story_{uuid.uuid4().hex}.{ext}"
        dest = self._stories_dir / filename
        dest.write_bytes(content)
        logger.info("Story image saved", extra={"filename": filename, "size": len(content)})

        return f"{self.settings.PUBLIC_MEDIA_BASE_URL}/stories/{filename}"
