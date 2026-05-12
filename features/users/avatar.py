"""Avatar download + face detection pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_S = 15.0
_TARGET_WIDTH = 600


@dataclass(frozen=True, slots=True)
class AvatarResult:
    """Outcome of the avatar processing pipeline."""

    avatar_path: str | None  # relative to MEDIA_DIR, e.g. "avatars/real_42.webp"
    is_aesthetic: bool       # True iff a face was detected


async def fetch_and_process_avatar(
    *,
    telegram_id: int,
    photo_url: str,
    media_dir: Path,
    avatars_subdir: str = "avatars",
) -> AvatarResult:
    """Download `photo_url`, run face detection, save WebP to disk.

    Returns `AvatarResult(None, False)` if the URL is empty or the pipeline
    failed at any step. Never raises — errors are logged and absorbed so the
    caller can use this from a background task safely.
    """
    if not photo_url:
        return AvatarResult(None, False)

    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT_S, follow_redirects=True
        ) as client:
            resp = await client.get(photo_url)
            if resp.status_code != 200:
                logger.warning(
                    "Avatar download failed",
                    extra={"telegram_id": telegram_id, "status": resp.status_code},
                )
                return AvatarResult(None, False)
            image_bytes = resp.content
    except Exception as exc:
        logger.warning(
            "Avatar download error",
            extra={"telegram_id": telegram_id, "error": str(exc)},
        )
        return AvatarResult(None, False)

    # Lazy imports — Pillow / OpenCV / numpy are heavy and only needed here.
    try:
        import cv2  # noqa: WPS433  (intentional lazy import)
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        logger.error(
            "Avatar pipeline dependencies missing",
            extra={"error": str(exc)},
        )
        return AvatarResult(None, False)

    try:
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        img_rgb = np.array(image)
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = face_cascade.detectMultiScale(
            img_gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
        )
        is_aesthetic = len(faces) > 0

        if image.width > _TARGET_WIDTH:
            ratio = _TARGET_WIDTH / float(image.width)
            new_h = int(image.height * ratio)
            image = image.resize(
                (_TARGET_WIDTH, new_h), Image.Resampling.LANCZOS
            )

        avatars_dir = media_dir / avatars_subdir
        avatars_dir.mkdir(parents=True, exist_ok=True)
        filename = f"real_{telegram_id}.webp"
        save_path = avatars_dir / filename
        image.save(save_path, "WEBP", quality=85)

        return AvatarResult(
            avatar_path=f"{avatars_subdir}/{filename}",
            is_aesthetic=is_aesthetic,
        )
    except Exception as exc:
        logger.error(
            "Avatar processing failed",
            extra={"telegram_id": telegram_id, "error": str(exc)},
        )
        return AvatarResult(None, False)
