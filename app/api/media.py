"""
Secure Media Serving — Anti-Path Traversal endpoint.

CRITICAL SECURITY:
  - NO StaticFiles mount (insecure).
  - Filename validated by strict regex (alphanumeric, underscores, dashes only).
  - Resolved path checked to be INSIDE the authorized media directory.
  - Does NOT require X-API-Key (img tags can't send custom headers).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Path as FastApiPath, status
from fastapi.responses import FileResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["media"])

# Strict pattern: alphanumeric, underscores, dashes, optional safe subdirectories, + image extension.
# NO slashes at the beginning, NO dots except before extension, NO path traversal characters.
_FILEPATH_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*\.(jpg|jpeg|png|webp)$")

# MIME mapping
_CONTENT_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@router.get(
    "/media/{file_path:path}",
    summary="Serve event images securely",
    description="Validates path and serves images with anti-path-traversal protection.",
    responses={
        200: {"description": "Image file"},
        400: {"description": "Invalid file path format"},
        403: {"description": "Path traversal attempt detected"},
        404: {"description": "File not found"},
    },
)
async def get_media(file_path: str = FastApiPath(...)) -> FileResponse:
    """
    Serve a media file with strict security validation.

    1. Validate path against regex (safe subdirectories allowed, no dot-segments).
    2. Resolve absolute path and verify it's inside BASE_MEDIA_DIR.
    3. Return FileResponse with cache and security headers.
    """
    # ── 1. Regex validation ──────────────────────────────────────────
    if not _FILEPATH_PATTERN.match(file_path):
        logger.warning("🚫 Rejected invalid file path: %s", file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format. Only alphanumeric, underscores, dashes, safe subdirectories, and .jpg/.jpeg/.png/.webp allowed.",
        )

    # ── 2. Path traversal protection ─────────────────────────────────
    settings = get_settings()
    base_dir = Path(settings.MEDIA_DIR).resolve()
    resolved_file_path = (base_dir / file_path).resolve()

    # Ensure resolved path is strictly inside the authorized directory
    if not str(resolved_file_path).startswith(str(base_dir)):
        logger.critical(
            "🔴 PATH TRAVERSAL ATTEMPT: file_path=%s resolved=%s base=%s",
            file_path,
            resolved_file_path,
            base_dir,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden.",
        )

    # ── 3. File existence check ──────────────────────────────────────
    if not resolved_file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    # ── 4. Serve with security headers ───────────────────────────────
    suffix = resolved_file_path.suffix.lower()
    content_type = _CONTENT_TYPES.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(resolved_file_path),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=864000",
            "X-Content-Type-Options": "nosniff",
        },
    )
