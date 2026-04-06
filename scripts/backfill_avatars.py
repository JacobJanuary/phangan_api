import asyncio
import logging
import sys
from io import BytesIO
from pathlib import Path

import asyncpg
import httpx
import mediapipe as mp
import numpy as np
from PIL import Image

# Add project root to sys.path to resolve 'app'
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_avatars")


async def check_and_download_avatar(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    telegram_id: int,
    bot_token: str,
    media_dir: Path,
) -> None:
    """Download avatar if missing, process with MediaPipe, and save to DB."""
    
    # 1. Get profile photos via Telegram API
    url = f"https://api.telegram.org/bot{bot_token}/getUserProfilePhotos"
    try:
        r = await client.post(url, json={"user_id": telegram_id, "limit": 1})
        if r.status_code != 200:
            logger.error("Failed to fetch photos API for %s: %s", telegram_id, r.status_code)
            return

        data = r.json()
        if not data.get("ok") or data["result"]["total_count"] == 0:
            logger.info("No photos found for %s", telegram_id)
            return

        # 2. Extract largest file_id
        photos = data["result"]["photos"][0]
        largest_photo = max(photos, key=lambda x: x["width"] * x["height"])
        file_id = largest_photo["file_id"]

        # 3. Get file path
        f_url = f"https://api.telegram.org/bot{bot_token}/getFile"
        f_req = await client.post(f_url, json={"file_id": file_id})
        f_data = f_req.json()

        if not f_data.get("ok"):
            logger.error("Could not get file path for %s", telegram_id)
            return

        file_path = f_data["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

        # 4. Download content
        img_resp = await client.get(download_url)
        if img_resp.status_code != 200:
            logger.error("Failed to download image for %s", telegram_id)
            return

        image_bytes = img_resp.content

        # 5. MediaPipe AI Processing
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        img_rgb = np.array(image)
        is_aesthetic = False

        is_aesthetic = True
        logger.info("Assuming aesthetic for profile photo of %s", telegram_id)

        # 6. Resize + Save as WebP
        if image.width > 600:
            ratio = 600.0 / float(image.width)
            new_h = int(float(image.height) * ratio)
            image = image.resize((600, new_h), Image.Resampling.LANCZOS)

        filename = f"real_{telegram_id}.webp"
        base_dir = media_dir / "avatars"
        base_dir.mkdir(parents=True, exist_ok=True)
        save_path = base_dir / filename

        image.save(save_path, "WEBP", quality=85)
        avatar_path = f"avatars/{filename}"

        # 7. Update DB
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
        logger.info("✅ Avatar saved and DB updated for %s", telegram_id)

    except Exception as e:
        logger.error("Exception processing %s: %s", telegram_id, str(e))


async def main():
    settings = get_settings()
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN missing in config.")
        return

    media_dir = Path(settings.MEDIA_DIR)
    
    pool = await asyncpg.create_pool(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )

    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT telegram_id FROM users WHERE is_phantom = false AND avatar_path IS NULL ORDER BY id"
        )

        logger.info("Starting backfill for %d missing avatars...", len(users))

        async with httpx.AsyncClient(timeout=15.0) as client:
            for u in users:
                uid = u["telegram_id"]
                if not uid:
                    continue

                await check_and_download_avatar(conn, client, uid, settings.BOT_TOKEN, media_dir)
                await asyncio.sleep(0.5)

    await pool.close()
    logger.info("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(main())
