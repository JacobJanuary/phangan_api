"""
Background worker for processing new Telegram users.
Executes AI-based gender detection and image processing pipeline.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import httpx
import asyncpg
import mediapipe as mp
from PIL import Image
from anthropic import AsyncAnthropic

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def detect_gender(first_name: str) -> str:
    """Uses Google GenAI to detect gender based on first name."""
    settings = get_settings()
    if not settings.KIMI_CODE_API_KEY:
        logger.warning("KIMI_CODE_API_KEY not set. Defaulting gender to male.")
        return "male"

    try:
        client = AsyncAnthropic(
            api_key=settings.KIMI_CODE_API_KEY,
            base_url="https://api.kimi.com/coding/",
            default_headers={"User-Agent": "ClaudeCode/1.0"}
        )
        prompt = f"Determine the most likely gender for the first name '{first_name}'. Reply strictly with either 'male' or 'female'."
        
        response = await client.messages.create(
            model="kimi-for-coding",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        
        ans = response.content[0].text.strip().lower()
        if "female" in ans:
            return "female"
        return "male"
    except Exception as e:
        logger.error("Gender detection failed: %s", e)
        return "male"


async def process_gender_background(
    pool: asyncpg.Pool,
    telegram_id: int,
    first_name: str,
) -> None:
    """Background task specifically for AI Gender Detection."""
    logger.info("Starting gender worker for telegram_id=%s", telegram_id)
    # 1. AI Gender Detection
    gender = await detect_gender(first_name)
    
    # 2. DB Update
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET gender = $1
                WHERE telegram_id = $2
                """,
                gender,
                telegram_id,
            )
        logger.info("Gender worker completed for telegram_id=%s: %s", telegram_id, gender)
    except Exception as e:
        logger.error("DB update failed for gender %s: %s", telegram_id, e)

async def process_avatar_background(
    pool: asyncpg.Pool,
    telegram_id: int,
    photo_url: str,
) -> None:
    """Background task specifically for image downloading and CV2 processing."""
    if not photo_url:
        return
        
    logger.info("Starting avatar worker for telegram_id=%s", telegram_id)
    settings = get_settings()

    is_aesthetic = False
    avatar_path = None

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(photo_url)
            if resp.status_code == 200:
                image_bytes = resp.content

                # MediaPipe Face Detection (BlazeFace)
                image = Image.open(BytesIO(image_bytes))
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                import numpy as np
                img_rgb = np.array(image)

                with mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=0.7
                ) as detector:
                    result = detector.process(img_rgb)
                    if result.detections:
                        confidence = result.detections[0].score[0]
                        is_aesthetic = confidence > 0.85
                        logger.info(
                            "Face detected for %s: confidence=%.2f, aesthetic=%s",
                            telegram_id, confidence, is_aesthetic,
                        )

                # Resize + save as WebP
                if image.width > 600:
                    ratio = 600.0 / float(image.width)
                    new_h = int(float(image.height) * ratio)
                    image = image.resize((600, new_h), Image.Resampling.LANCZOS)

                filename = f"real_{telegram_id}.webp"
                base_dir = Path(settings.MEDIA_DIR) / "avatars"
                base_dir.mkdir(parents=True, exist_ok=True)
                save_path = base_dir / filename

                image.save(save_path, "WEBP", quality=85)
                avatar_path = f"avatars/{filename}"
            else:
                logger.warning("Failed to download image for %s. Status: %s", telegram_id, resp.status_code)
    except Exception as e:
        logger.error("Image pipeline failed for %s: %s", telegram_id, e)

    # DB Update (Avatar)
    try:
        if avatar_path:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE users
                    SET is_aesthetic = $1, avatar_path = $2
                    WHERE telegram_id = $3
                    """,
                    is_aesthetic,
                    avatar_path,
                    telegram_id,
                )
            logger.info("Avatar worker completed for telegram_id=%s", telegram_id)
    except Exception as e:
        logger.error("DB update failed for avatar %s: %s", telegram_id, e)
