"""Cascading gender detection.

Layers:
  1. Dictionary lookup (instant, free, ~90% RU coverage)
  2. Emoji/non-letter check → 'unknown'
  3. Morphological analysis of Cyrillic name endings (instant, free)
  4. LLM fallback through `shared.ai` (1–2 sec)
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from shared.ai.cascade import CascadeOrchestrator
from shared.ai.ports import CompletionRequest

from features.users.name_dictionaries import (
    FEMALE_NAMES_INT,
    FEMALE_NAMES_RU,
    MALE_NAMES_INT,
    MALE_NAMES_RU,
)

logger = logging.getLogger(__name__)

Gender = Literal["male", "female", "unknown"]

_LETTER_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ]")
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")

# Feminine endings, longer first for specificity.
_FEMALE_SUFFIXES: tuple[str, ...] = (
    "ия", "ья", "на", "ла", "та", "да", "ра", "за", "са", "ка", "ша",
    "жа", "га", "ва", "ня", "ля", "ся", "а", "я",
)
_MALE_SUFFIXES: tuple[str, ...] = (
    "ей", "ий", "ай", "ой", "ёр", "ор", "ан", "он", "ён", "им", "ис",
    "ит", "ёб", "еб", "ур", "рк", "ил", "ёг", "ег", "ав",
)


def _first_word(name: str) -> str:
    parts = name.strip().split()
    return parts[0] if parts else name


def lookup_dictionary(name: str) -> Gender | None:
    low = name.strip().lower()
    if low in FEMALE_NAMES_RU or low in FEMALE_NAMES_INT:
        return "female"
    if low in MALE_NAMES_RU or low in MALE_NAMES_INT:
        return "male"
    return None


def has_letters(name: str) -> bool:
    return bool(_LETTER_RE.search(name))


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text))


def guess_by_morphology(name: str) -> Gender | None:
    """Cyrillic-only morphological heuristic. None if not applicable."""
    if not has_cyrillic(name):
        return None

    low = re.sub(r"@\S+", "", name.strip().lower()).strip()
    first = _first_word(low)
    if len(first) < 2:
        return None

    for suffix in _FEMALE_SUFFIXES:
        if first.endswith(suffix):
            return "female"
    for suffix in _MALE_SUFFIXES:
        if first.endswith(suffix):
            return "male"

    last_char = first[-1]
    if re.match(r"[а-яё]", last_char) and last_char not in "аеёиоуыэюя":
        return "male"
    return None


async def detect_gender_via_ai(
    first_name: str,
    *,
    language: str,
    cascade: CascadeOrchestrator,
) -> Gender:
    """Layer 4 — ask the AI cascade. Always returns male/female (never unknown)."""
    lang_hint = "Russian" if language == "ru" else "English"
    request = CompletionRequest(
        system="You are a name gender classifier. Reply with only 'male' or 'female'.",
        user=(
            f"The user's Telegram language is {lang_hint}. "
            f"Determine the most likely gender for the name '{first_name}'. "
            f"Reply strictly with either 'male' or 'female'."
        ),
        max_tokens=10,
    )
    try:
        answer = (await cascade.complete(request)).strip().lower()
    except Exception as exc:  # cascade exhausted
        logger.error(
            "Gender detection AI cascade failed — defaulting to male",
            extra={"name": first_name, "error": str(exc)},
        )
        return "male"
    return "female" if "female" in answer else "male"


async def detect_gender(
    first_name: str,
    *,
    language: str = "en",
    cascade: CascadeOrchestrator | None = None,
) -> Gender:
    """Run the full cascade."""
    clean = _first_word(first_name) if first_name.strip() else first_name

    if (result := lookup_dictionary(clean)) is not None:
        logger.info("Gender via dictionary", extra={"name": first_name, "gender": result})
        return result

    if not has_letters(first_name):
        logger.info("Gender unknown (no letters)", extra={"name": first_name})
        return "unknown"

    if (result := guess_by_morphology(clean)) is not None:
        logger.info("Gender via morphology", extra={"name": first_name, "gender": result})
        return result

    if cascade is None:
        logger.warning(
            "Gender cascade not configured — defaulting to male",
            extra={"name": first_name},
        )
        return "male"

    result = await detect_gender_via_ai(first_name, language=language, cascade=cascade)
    logger.info("Gender via AI", extra={"name": first_name, "gender": result})
    return result
