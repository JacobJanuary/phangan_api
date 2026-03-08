#!/usr/bin/env python3
"""
Phantom Avatar Generator — Gemini AI Pipeline.

Generates realistic travel-lifestyle avatar images for 100 phantom users.

Phase 1: Gemini 3 Flash → unique image prompt per user (name + gender + scene)
Phase 2: gemini-3.1-flash-image-preview → image generation → WebP → DB update

Usage:
    cd /path/to/phangan_api
    python scripts/generate_phantom_avatars.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
import time
from io import BytesIO
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from PIL import Image
from google import genai

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phantom_gen")

# ── Scene pool ───────────────────────────────────────────────────────────────
SCENES = [
    "standing on a tropical white sand beach at golden hour sunset, ocean waves in the background",
    "relaxing on a terrace of a luxury tropical villa overlooking the sea, palm trees around",
    "at a cozy tiki beach bar with string lights, tropical cocktail on the counter",
    "at a scenic viewpoint overlooking a tropical island panorama, lush green hills and blue sea",
    "on a wooden pier extending into turquoise tropical water, boats in the distance",
    "in a tropical garden with blooming frangipani flowers and banana trees",
    "at an outdoor yoga space on a clifftop overlooking the ocean, morning light",
    "walking down a palm-lined tropical road, motorbike parked nearby, golden light filtering through trees",
]

FEMALE_STYLES = [
    "wearing a light summer dress",
    "wearing a colorful tropical print outfit",
    "wearing a casual resort wear top and shorts",
    "wearing a flowy bohemian dress",
    "wearing a light linen beach outfit",
]

MALE_STYLES = [
    "wearing an unbuttoned linen shirt and shorts",
    "wearing a casual tropical print shirt",
    "wearing a tank top and board shorts",
    "wearing a simple t-shirt and linen pants",
    "wearing a casual resort polo shirt",
]


def _build_meta_prompt(name: str, gender: str) -> str:
    """Build the Phase 1 meta-prompt for Gemini 3 Flash."""
    age_range = "20-29 years old" if gender == "female" else "25-40 years old"
    pronoun = "woman" if gender == "female" else "man"

    return f"""You are a creative director for a travel lifestyle photography brand. 
Generate a single detailed image prompt for an AI image generator. 

Subject: A {pronoun} named {name}, {age_range}, with a natural attractive appearance.
The person should look like a real traveler/tourist on a tropical island in Thailand.

Requirements for the prompt you generate:
- Describe the person's appearance naturally (hair color/style, skin tone, build) — make it diverse and realistic
- Include specific photography details: camera angle, lighting, depth of field
- The mood should be warm, happy, adventurous — like a travel Instagram post
- Include a specific tropical Koh Phangan scene/background
- Mention clothing appropriate for a tropical island
- Do NOT mention any brand names
- The prompt should produce a single person portrait (head to waist or full body)

Output ONLY the image prompt, nothing else. No quotes, no explanations."""


def _build_image_prompt(text_prompt: str) -> str:
    """Wrap the Phase 1 output with photography framing for Phase 2."""
    return (
        f"Professional travel lifestyle photography. {text_prompt} "
        f"Shot with natural lighting, warm tropical color grading. "
        f"Shallow depth of field, bokeh background. "
        f"High quality, detailed, 8K resolution. Photorealistic style."
    )


def _build_fallback_prompt(name: str, gender: str, attempt: int) -> str:
    """Build progressively simpler prompts for safety filter retries."""
    age_range = "20-29" if gender == "female" else "25-40"
    pronoun = "woman" if gender == "female" else "man"
    scene = random.choice(SCENES)
    style = random.choice(FEMALE_STYLES if gender == "female" else MALE_STYLES)

    if attempt == 1:
        return (
            f"Professional travel lifestyle portrait of a {pronoun}, {age_range} years old, "
            f"{style}, {scene}. "
            f"Natural golden hour lighting, warm color grading, shallow depth of field. "
            f"High quality photorealistic style, 8K."
        )
    elif attempt == 2:
        return (
            f"Portrait of a friendly {pronoun}, {age_range} years old, "
            f"in a beautiful tropical setting with palm trees and ocean. "
            f"Warm natural lighting, travel photography style."
        )
    else:
        return (
            f"Digital art portrait of a {pronoun} traveler in a tropical paradise. "
            f"Warm colors, golden light, palm trees, ocean view. "
            f"High quality illustration style."
        )


async def generate_one(
    client: genai.Client,
    user_id: int,
    name: str,
    gender: str,
    output_dir: Path,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Generate avatar for a single phantom user. Returns (success, message)."""

    # Phase 1: Generate unique prompt via Gemini 3 Flash
    try:
        meta_prompt = _build_meta_prompt(name, gender)
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=meta_prompt,
        )
        image_prompt = _build_image_prompt(response.text.strip())
        logger.info("  Phase 1 OK: prompt generated (%d chars)", len(image_prompt))
    except Exception as e:
        logger.warning("  Phase 1 FAIL: %s — using fallback prompt", e)
        image_prompt = _build_fallback_prompt(name, gender, attempt=1)

    if dry_run:
        logger.info("  [DRY RUN] Would generate image with prompt: %s", image_prompt[:100])
        return True, "dry_run"

    # Phase 2: Generate image with cascade retry
    max_attempts = 3
    for attempt in range(max_attempts):
        prompt = image_prompt if attempt == 0 else _build_fallback_prompt(name, gender, attempt)

        try:
            response = await client.aio.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=prompt,
            )

            # Extract image from response
            for part in response.parts:
                if part.inline_data is not None:
                    # Decode image bytes to PIL
                    img_bytes = part.inline_data.data
                    image = Image.open(BytesIO(img_bytes))
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")

                    # Resize if needed
                    if image.width > 600:
                        ratio = 600.0 / image.width
                        new_h = int(image.height * ratio)
                        image = image.resize((600, new_h), Image.Resampling.LANCZOS)

                    # Save as WebP
                    filename = f"phantom_{user_id}.webp"
                    save_path = output_dir / filename
                    image.save(save_path, "WEBP", quality=85)
                    logger.info("  Phase 2 OK: saved %s (%dx%d)", filename, image.width, image.height)
                    return True, f"avatars/{filename}"

            logger.warning("  Phase 2: no image in response (attempt %d/%d)", attempt + 1, max_attempts)

        except Exception as e:
            error_msg = str(e)
            if "SAFETY" in error_msg.upper() or "blocked" in error_msg.lower():
                logger.warning("  Phase 2: safety filter (attempt %d/%d)", attempt + 1, max_attempts)
            else:
                logger.error("  Phase 2: error (attempt %d/%d): %s", attempt + 1, max_attempts, e)

        # Wait before retry
        await asyncio.sleep(2)

    return False, "all_attempts_failed"


async def main():
    parser = argparse.ArgumentParser(description="Generate phantom avatars")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of phantoms (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Only generate prompts, skip images")
    parser.add_argument("--offset", type=int, default=0, help="Start from Nth phantom")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set!")
        sys.exit(1)

    # Setup output directory
    output_dir = Path(settings.MEDIA_DIR) / "avatars"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connect to DB
    conn = await asyncpg.connect(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )

    # Fetch phantoms
    query = "SELECT id, first_name, gender FROM users WHERE is_phantom = true ORDER BY id"
    if args.limit > 0:
        query += f" LIMIT {args.limit} OFFSET {args.offset}"
    phantoms = await conn.fetch(query)

    logger.info("=" * 60)
    logger.info("Phantom Avatar Generator")
    logger.info("Phantoms to process: %d", len(phantoms))
    logger.info("Output dir: %s", output_dir)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("=" * 60)

    # Init Gemini client
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    success = 0
    failed = 0
    skipped = 0

    for i, row in enumerate(phantoms, 1):
        user_id = row["id"]
        name = row["first_name"]
        gender = row["gender"]

        # Skip if avatar already exists
        existing_path = output_dir / f"phantom_{user_id}.webp"
        if existing_path.exists():
            logger.info("[%d/%d] SKIP id=%d %s — file exists", i, len(phantoms), user_id, name)
            skipped += 1
            continue

        logger.info("[%d/%d] Generating id=%d %s (%s)", i, len(phantoms), user_id, name, gender)

        ok, result = await generate_one(client, user_id, name, gender, output_dir, args.dry_run)

        if ok and not args.dry_run:
            # Update DB
            await conn.execute(
                "UPDATE users SET avatar_path = $1 WHERE id = $2",
                result, user_id,
            )
            success += 1
            logger.info("  DB updated: avatar_path = %s", result)
        elif ok:
            success += 1
        else:
            failed += 1
            logger.error("  FAILED: %s", result)

        # Rate limiting: 1.5-2.5 sec between requests
        if i < len(phantoms):
            delay = random.uniform(1.5, 2.5)
            await asyncio.sleep(delay)

    await conn.close()

    logger.info("=" * 60)
    logger.info("DONE: %d success, %d failed, %d skipped", success, failed, skipped)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
