"""Cascading language detection (en/ru only for now).

Layers:
  1. Cyrillic in name → 'ru'
  2. Telegram `language_code` contains 'ru' → 'ru'
  3. Name in distinctly-Russian dictionary → 'ru'
  4. Telegram getChat → bio/last_name has Cyrillic
  5. Default → 'en'
"""

from __future__ import annotations

import logging

import httpx

from features.users.gender_detection import has_cyrillic
from features.users.name_dictionaries import (
    FEMALE_NAMES_RU,
    MALE_NAMES_RU,
    RU_LATIN_NAMES,
)

logger = logging.getLogger(__name__)


def name_in_ru_dict(first_name: str) -> bool:
    low = first_name.strip().lower()
    if low in FEMALE_NAMES_RU or low in MALE_NAMES_RU:
        return True
    return low in RU_LATIN_NAMES


def detect_language_sync(first_name: str, telegram_language_code: str) -> str:
    """Synchronous fast-path covering layers 1–3 (no network)."""
    if has_cyrillic(first_name):
        return "ru"
    if "ru" in str(telegram_language_code).lower():
        return "ru"
    clean = first_name.strip().split()[0] if first_name.strip() else first_name
    if name_in_ru_dict(clean):
        return "ru"
    return "en"


async def fetch_bio_language(*, telegram_id: int, bot_token: str) -> str | None:
    """Layer 4 — Telegram `getChat`. Returns 'ru' if bio/last_name is Cyrillic."""
    if not bot_token:
        return None
    url = f"https://api.telegram.org/bot{bot_token}/getChat"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json={"chat_id": telegram_id})
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "getChat failed",
            extra={"telegram_id": telegram_id, "error": str(exc)},
        )
        return None

    if not data.get("ok"):
        return None
    result = data.get("result", {}) or {}
    bio = result.get("bio") or ""
    last_name = result.get("last_name") or ""
    if has_cyrillic(bio) or has_cyrillic(last_name):
        return "ru"
    return None


async def detect_language(
    first_name: str,
    *,
    telegram_language_code: str,
    telegram_id: int | None = None,
    bot_token: str = "",
) -> str:
    """Full 5-layer cascade."""
    fast = detect_language_sync(first_name, telegram_language_code)
    if fast == "ru":
        return "ru"
    if telegram_id is not None and bot_token:
        bio_lang = await fetch_bio_language(
            telegram_id=telegram_id, bot_token=bot_token
        )
        if bio_lang:
            return bio_lang
    return "en"
