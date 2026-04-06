"""
Share Card Generator — renders a 1080×1920 Story PNG using Pillow.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
SHARE_DIR = Path("/home/ubuntu/Phangan/TG_parcer/media/share")
MEDIA_BASE = "https://api.fastpump.fun/api/media/share"

FONT_BOLD   = str(FONT_DIR / "Inter-Bold.ttf")
FONT_MEDIUM = str(FONT_DIR / "Inter-Medium.ttf")
FONT_REG    = str(FONT_DIR / "Inter-Regular.ttf")

# ── Canvas size (Telegram/IG Story) ──────────────────────────────────────────
W, H = 1080, 1920

# ── Category emoji map ───────────────────────────────────────────────────────
CAT_EMOJI = {
    "sport": "🏋️", "party": "🎉", "chill": "🧘", "music": "🎵",
    "food": "🍜", "market": "🛍", "workshop": "🎨", "community": "🤝",
}

# ── Colors ───────────────────────────────────────────────────────────────────
BG_TOP       = (6, 8, 20)
BG_BOTTOM    = (18, 6, 32)
CYAN         = (0, 243, 255)
PURPLE       = (140, 50, 255)
WHITE        = (255, 255, 255)
WHITE_70     = (255, 255, 255, 178)
WHITE_50     = (255, 255, 255, 128)
WHITE_30     = (255, 255, 255, 76)
CARD_BG      = (255, 255, 255, 15)
GREEN        = (74, 222, 128)


def _gradient_bg(draw: ImageDraw.Draw) -> None:
    """Draw vertical gradient from dark navy to dark purple."""
    for y in range(H):
        ratio = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _rounded_rect(draw: ImageDraw.Draw, xy: tuple, radius: int, fill) -> None:
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def generate_share_card(
    plan_name: str,
    date: str,
    total_events: int,
    total_travel_km: float,
    timeline: list[dict],
    user_id: int,
) -> str:
    """
    Render a share card PNG and return its public URL.
    
    timeline items: {start_time, title, location, category, price_thb}
    """
    SHARE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Create RGBA image ─────────────────────────────────────────────────
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # ── Background gradient ───────────────────────────────────────────────
    _gradient_bg(draw)

    # ── Load fonts ────────────────────────────────────────────────────────
    try:
        f_title  = ImageFont.truetype(FONT_BOLD, 56)
        f_plan   = ImageFont.truetype(FONT_BOLD, 44)
        f_meta   = ImageFont.truetype(FONT_MEDIUM, 32)
        f_time   = ImageFont.truetype(FONT_BOLD, 36)
        f_event  = ImageFont.truetype(FONT_BOLD, 34)
        f_loc    = ImageFont.truetype(FONT_REG, 28)
        f_footer = ImageFont.truetype(FONT_MEDIUM, 26)
    except Exception:
        logger.warning("Inter font not found, using default")
        f_title = f_plan = f_meta = f_time = f_event = f_loc = f_footer = ImageFont.load_default()

    # ── Header: Vibe Pilot ────────────────────────────────────────────────
    y = 120
    # Compass icon circle
    cx = W // 2
    draw.ellipse((cx - 45, y - 10, cx + 45, y + 80), fill=(0, 243, 255, 30))
    draw.text((cx, y + 35), "🧭", font=f_title, fill=WHITE, anchor="mm")
    y += 110

    # "Vibe Pilot" title
    draw.text((cx, y), "Vibe Pilot", font=f_title, fill=CYAN, anchor="mt")
    y += 80

    # ── Plan name ─────────────────────────────────────────────────────────
    # Word-wrap plan name
    plan_clean = plan_name.replace("🧭", "").strip()
    draw.text((cx, y), plan_clean, font=f_plan, fill=WHITE, anchor="mt")
    y += 65

    # Date + stats
    stats = f"{date}  ·  {total_events} событий  ·  {total_travel_km} км"
    draw.text((cx, y), stats, font=f_meta, fill=WHITE_50, anchor="mt")
    y += 80

    # ── Divider ───────────────────────────────────────────────────────────
    draw.line([(100, y), (W - 100, y)], fill=(0, 243, 255, 40), width=2)
    y += 40

    # ── Timeline ──────────────────────────────────────────────────────────
    max_items = min(len(timeline), 5)  # Max 5 items to fit
    card_h = 160
    pad = 60
    line_x = 140  # Vertical line x position

    for i in range(max_items):
        item = timeline[i]
        card_y = y

        # Vertical line segment
        if i < max_items - 1:
            draw.line(
                [(line_x, card_y + 20), (line_x, card_y + card_h + 20)],
                fill=(0, 243, 255, 60), width=3
            )

        # Dot on timeline
        dot_r = 10
        draw.ellipse(
            (line_x - dot_r, card_y + 15 - dot_r, line_x + dot_r, card_y + 15 + dot_r),
            fill=CYAN
        )

        # Card background
        card_x = line_x + 35
        _rounded_rect(draw, (card_x, card_y - 5, W - pad, card_y + card_h - 15), 20, CARD_BG)

        # Time
        time_str = item.get("start_time", "TBD")
        draw.text((card_x + 20, card_y + 12), time_str, font=f_time, fill=CYAN)

        # Title
        cat = item.get("category", "").lower()
        emoji = CAT_EMOJI.get(cat, "📌")
        title = f"{emoji}  {item.get('title', '')}"
        # Truncate if too long
        if len(title) > 28:
            title = title[:25] + "..."
        draw.text((card_x + 130, card_y + 14), title, font=f_event, fill=WHITE)

        # Location
        loc = item.get("location", "")
        if len(loc) > 30:
            loc = loc[:27] + "..."
        price = item.get("price_thb", 0)
        price_str = f"{price} ฿" if price > 0 else "FREE"
        loc_text = f"📍 {loc}  ·  {price_str}"
        draw.text((card_x + 20, card_y + 70), loc_text, font=f_loc, fill=WHITE_50)

        # Travel distance (if not first)
        if i > 0:
            travel_km = item.get("travel_from_previous_km", 0)
            if travel_km > 0:
                draw.text((card_x + 20, card_y + 108), f"🛵 {travel_km} km", font=f_loc, fill=WHITE_30)

        y += card_h + 10

    # ── Footer ────────────────────────────────────────────────────────────
    y = H - 160
    draw.line([(100, y), (W - 100, y)], fill=(0, 243, 255, 40), width=2)
    y += 40
    draw.text((cx, y), "Составлено AI  ·  VibeRadar", font=f_footer, fill=WHITE_50, anchor="mt")
    y += 45
    draw.text((cx, y), "Составь свой план 👉 @VibeRadarBot", font=f_footer, fill=CYAN, anchor="mt")

    # ── Save ──────────────────────────────────────────────────────────────
    uid_hash = hashlib.md5(f"{user_id}_{date}_{plan_name}".encode()).hexdigest()[:8]
    filename = f"plan_{user_id}_{date}_{uid_hash}.png"
    filepath = SHARE_DIR / filename
    
    # Convert RGBA to RGB for PNG (no transparency needed)
    img_rgb = Image.new("RGB", (W, H), (0, 0, 0))
    img_rgb.paste(img, mask=img.split()[3])
    img_rgb.save(filepath, "PNG", optimize=True)

    url = f"{MEDIA_BASE}/{filename}"
    logger.info(f"Share card generated: {url}")
    return url
