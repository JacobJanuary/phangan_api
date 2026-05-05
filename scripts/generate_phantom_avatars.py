#!/usr/bin/env python3
"""
Phantom Avatar Generator v4 — Gemini + Imagen AI Pipeline.

Generates realistic travel-lifestyle avatar images for 100 phantom users.

Phase 1: Gemini 3 Flash → unique image prompt (name + gender + mood + random variety)
Phase 2: Imagen 4.0 Fast → image (with person_generation=ALLOW_ADULT)
         Fallback: Imagen 4.0 → Gemini 3.1 Flash Image

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
from io import BytesIO
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from PIL import Image
from anthropic import AsyncAnthropic

from core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phantom_gen")

# ── Variety pools ─────────────────────────────────────────────────────────────
POSES = [
    "laughing with head slightly tilted back",
    "looking slightly to the side with a relaxed smile",
    "resting chin on hand, warm smile",
    "brushing hair back with one hand, candid moment",
    "looking at camera with a confident grin",
    "caught mid-laugh, eyes slightly squinted",
    "gazing into the distance with a soft smile",
    "leaning against a railing, relaxed pose",
    "sunglasses pushed up on head, smiling",
    "holding a tropical drink, turning toward camera",
]

ANGLES = [
    "shot slightly from below, heroic feel",
    "three-quarter face view, slightly turned",
    "straight-on eye contact, intimate feel",
    "slight side profile, looking back over shoulder",
    "shot from slightly above, soft and approachable",
    "natural selfie angle, warm and casual",
]

# ── Mood-specific scene details (from old Phantom Protocol) ──────────────────
MOOD_SCENES = {
    "party": [
        "dark jungle rave background, neon purple and red lighting, sweaty glowing skin, blurry dancing crowd behind",
        "beach party with fire dancers in background, warm orange glow, festive energy",
        "rooftop bar at night, city lights and ocean behind, cocktail atmosphere",
        "full moon party beach, colorful lights reflecting on water, night energy",
    ],
    "spiritual": [
        "zen morning beach at golden hour, peaceful serene aura, organic natural feel",
        "yoga retreat terrace with ocean view, early morning soft mist",
        "tropical garden with incense smoke, warm peaceful golden light",
        "meditation spot on cliff overlooking ocean, sunrise light",
    ],
    "business": [
        "trendy tropical coworking cafe, bright daytime, laptop edge slightly visible",
        "modern villa workspace with sea view through window, clean bright light",
        "stylish beach cafe, macbook blurred in background, professional casual vibe",
        "co-living space terrace, morning coffee, productive energy",
    ],
}

# Fallback for phantoms without mood
MOOD_SCENES[None] = [
    "blurred tropical sunset over ocean",
    "lush green jungle foliage, dappled sunlight",
    "palm tree silhouettes against golden sky",
]

LIGHTING = [
    "warm golden hour sunlight on face",
    "soft diffused morning light",
    "dramatic sunset backlight with rim light on hair",
    "dappled light through palm leaves",
    "warm ambient glow from string lights",
    "natural shade with bright tropical background",
]

FEMALE_STYLES = [
    "wearing a light summer dress",
    "wearing a colorful tropical print top",
    "wearing an off-shoulder bohemian blouse",
    "in a casual crop top",
    "wearing a strappy tank top",
    "wearing a festival outfit",
]

MALE_STYLES = [
    "wearing an unbuttoned linen shirt",
    "wearing a casual tropical print shirt",
    "wearing a fitted tank top",
    "wearing a simple t-shirt, sun-kissed skin",
    "shirtless, natural and athletic",
    "smart casual tropical wear",
]

# ── Image model ───────────────────────────────────────────────────────────────
IMAGE_MODEL = "gemini-3.1-flash-image-preview"


def _build_meta_prompt(name: str, gender: str, mood: str | None) -> str:
    """Build the Phase 1 meta-prompt for Gemini 3 Flash."""
    age_range = "20-29 years old" if gender == "female" else "25-40 years old"
    pronoun = "woman" if gender == "female" else "man"
    pose = random.choice(POSES)
    angle = random.choice(ANGLES)
    scene = random.choice(MOOD_SCENES.get(mood, MOOD_SCENES[None]))
    light = random.choice(LIGHTING)
    mood_label = mood or "traveler"

    return f"""You are a creative director making unique avatar photos for a social travel app on Koh Phangan.
Generate ONE detailed image prompt for an AI image generator.

Subject: A {pronoun} named {name}, {age_range}, attractive, natural look.
Personality: {mood_label} type — reflect this in their vibe and energy.
This is for a PROFILE AVATAR — face is the main focus, but it should feel CANDID and ALIVE, not like a passport photo.

Mandatory creative direction for THIS specific avatar:
- POSE: {pose}
- CAMERA: {angle}
- SCENE: {scene}
- LIGHTING: {light}

Requirements:
- Close-up portrait: head and shoulders, face fills ~50-60% of frame
- Style: raw, candid smartphone selfie feel — like an Instagram story, NOT studio photography
- Describe unique appearance: hair color/style, eye color, skin tone, visible skin texture
- Slightly tanned skin, natural imperfections, realistic amateur photography feel
- Square 1:1 format
- ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO LOGOS in the image
- Do NOT mention brand names

Output ONLY the image prompt, nothing else."""


def _build_image_prompt(text_prompt: str) -> str:
    """Wrap the Phase 1 output with selfie framing for Phase 2."""
    return (
        f"A raw, candid, unedited smartphone selfie portrait. {text_prompt} "
        f"Highly realistic amateur photography, visible skin texture, "
        f"Instagram story aesthetic. Close-up head and shoulders. "
        f"ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO LOGOS."
    )


def _build_fallback_prompt(name: str, gender: str, mood: str | None, attempt: int) -> str:
    """Build progressively simpler prompts for retries."""
    age_range = "20-29" if gender == "female" else "25-40"
    pronoun = "woman" if gender == "female" else "man"
    scene = random.choice(MOOD_SCENES.get(mood, MOOD_SCENES[None]))
    style = random.choice(FEMALE_STYLES if gender == "female" else MALE_STYLES)

    if attempt == 1:
        return (
            f"A raw, candid smartphone selfie of a beautiful {age_range} year old {pronoun}, "
            f"slightly tanned skin, {style}, {scene}. "
            f"Close-up headshot, face fills the frame, visible skin texture, "
            f"Instagram story style. NO TEXT, NO LOGOS."
        )
    elif attempt == 2:
        return (
            f"Close-up selfie portrait of a friendly {pronoun}, {age_range} years old. "
            f"Warm smile, blurred tropical background. "
            f"Natural lighting, candid feel. NO TEXT."
        )
    else:
        return (
            f"Portrait headshot of a {pronoun}, natural smile, "
            f"blurred green tropical background. Warm lighting. NO TEXT."
        )


def _process_and_save(image_bytes: bytes, user_id: int, output_dir: Path) -> tuple[str, int, int]:
    """Resize to 600px width max, convert to WebP, return (relative_path, w, h)."""
    image = Image.open(BytesIO(image_bytes))
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    if image.width > 600:
        ratio = 600.0 / image.width
        new_h = int(image.height * ratio)
        image = image.resize((600, new_h), Image.Resampling.LANCZOS)

    filename = f"phantom_{user_id}.webp"
    save_path = output_dir / filename
    image.save(save_path, "WEBP", quality=85)
    return f"avatars/{filename}", image.width, image.height


async def generate_one(
    client: AsyncAnthropic,
    user_id: int,
    name: str,
    gender: str,
    mood: str | None,
    output_dir: Path,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Generate avatar for a single phantom user. Returns (success, message)."""

    # Phase 1: Generate unique prompt via Kimi Code API
    image_prompt = None
    meta_prompt = _build_meta_prompt(name, gender, mood)
    for p1_attempt in range(5):
        try:
            response = await client.messages.create(
                model="kimi-for-coding",
                max_tokens=2048,
                messages=[{"role": "user", "content": meta_prompt}]
            )
            image_prompt = _build_image_prompt(response.content[0].text.strip())
            logger.info("  Phase 1 OK: prompt (%d chars)", len(image_prompt))
            break
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e).upper():
                logger.info("  Phase 1: 503 retry %d/5...", p1_attempt + 1)
                await asyncio.sleep(1)
            else:
                logger.warning("  Phase 1 FAIL: %s — using fallback", e)
                break
    if image_prompt is None:
        image_prompt = _build_fallback_prompt(name, gender, mood, attempt=1)
        logger.warning("  Phase 1: all retries failed, using fallback prompt")

    if dry_run:
        logger.info("  [DRY RUN] Prompt: %s", image_prompt[:120])
        return True, "dry_run"

    # Phase 2: Disabled since we migrated off Gemini and Kimi has no image generation yet.
    logger.error("  Phase 2 SKIP: Image generation disabled. Need an image provider (e.g., DALL-E). Generated Prompt: %s", image_prompt)
    return False, "image_generation_disabled"


CONCURRENCY = 10  # Number of parallel workers


async def main():
    parser = argparse.ArgumentParser(description="Generate phantom avatars")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of phantoms (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Only generate prompts, skip images")
    parser.add_argument("--offset", type=int, default=0, help="Start from Nth phantom")
    parser.add_argument("--workers", type=int, default=CONCURRENCY, help="Parallel workers")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.KIMI_CODE_API_KEY:
        logger.error("KIMI_CODE_API_KEY not set!")
        sys.exit(1)

    # Setup output directory
    output_dir = Path(settings.MEDIA_DIR) / "avatars"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connection pool for concurrent DB writes
    pool = await asyncpg.create_pool(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        min_size=2,
        max_size=args.workers + 2,
    )

    # Fetch phantoms
    async with pool.acquire() as conn:
        query = "SELECT id, first_name, gender, mood FROM users WHERE is_phantom = true ORDER BY id"
        if args.limit > 0:
            query += f" LIMIT {args.limit} OFFSET {args.offset}"
        phantoms = await conn.fetch(query)

    # Filter out already generated
    todo = []
    skipped = 0
    for row in phantoms:
        existing = output_dir / f"phantom_{row['id']}.webp"
        if existing.exists():
            skipped += 1
        else:
            todo.append(row)

    logger.info("=" * 60)
    logger.info("👻 Phantom Avatar Generator v4 — %d workers", args.workers)
    logger.info("Total: %d | Todo: %d | Skipped: %d", len(phantoms), len(todo), skipped)
    logger.info("Model: %s", IMAGE_MODEL)
    logger.info("Output: %s", output_dir)
    logger.info("=" * 60)

    if not todo:
        logger.info("Nothing to do!")
        await pool.close()
        return

    # Init Kimi client
    client = AsyncAnthropic(
        api_key=settings.KIMI_CODE_API_KEY,
        base_url="https://api.kimi.com/coding/",
        default_headers={"User-Agent": "ClaudeCode/1.0"}
    )

    # Concurrency control
    semaphore = asyncio.Semaphore(args.workers)
    success = 0
    failed = 0
    lock = asyncio.Lock()
    total = len(todo)

    async def worker(idx: int, row):
        nonlocal success, failed
        user_id = row["id"]
        name = row["first_name"]
        gender = row["gender"]
        mood = row["mood"]

        async with semaphore:
            logger.info("[%d/%d] 🎨 id=%d %s (%s/%s)", idx, total, user_id, name, gender, mood or "?")

            ok, result = await generate_one(client, user_id, name, gender, mood, output_dir, args.dry_run)

            if ok and not args.dry_run:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE users SET avatar_path = $1 WHERE id = $2",
                        result, user_id,
                    )
                async with lock:
                    success += 1
                logger.info("  ✅ id=%d DB updated: %s", user_id, result)
            elif ok:
                async with lock:
                    success += 1
            else:
                async with lock:
                    failed += 1
                logger.error("  ❌ id=%d FAILED: %s", user_id, result)

    # Launch all workers
    tasks = [worker(i, row) for i, row in enumerate(todo, 1)]
    await asyncio.gather(*tasks)

    await pool.close()

    logger.info("=" * 60)
    logger.info("🎉 DONE: %d success, %d failed, %d skipped", success, failed, skipped)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
