"""Media HTTP endpoints — serve images and accept story uploads."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Path as FastApiPath,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from core.config import Settings
from core.dependencies import get_settings_dep
from features.media.service import MediaService

router = APIRouter(prefix="/api", tags=["media"])


@router.get(
    "/media/{file_path:path}",
    summary="Serve event images securely",
    description="Validates path and serves images with anti-path-traversal protection.",
)
async def get_media(
    file_path: str = FastApiPath(...),
    settings: Settings = Depends(get_settings_dep),
) -> FileResponse:
    resolved = MediaService(settings=settings).resolve_for_serving(file_path)
    return FileResponse(
        path=str(resolved.absolute),
        media_type=resolved.content_type,
        headers={
            "Cache-Control": "public, max-age=864000",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/media/upload-story",
    summary="Upload generated story image",
    status_code=status.HTTP_201_CREATED,
)
async def upload_story_image(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    content = await file.read()
    url = await MediaService(settings=settings).save_story(
        content=content,
        content_type=file.content_type,
        original_filename=file.filename,
    )
    return {"url": url}
