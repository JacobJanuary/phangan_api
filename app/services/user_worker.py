"""
Background worker for processing new Telegram users.
Executes cascading gender detection and image processing pipeline.

Gender detection cascade:
  1. Dictionary lookup (TOP-100 Russian + common international names)
  2. Emoji / non-letter validation → "unknown"
  3. Morphological analysis of Russian name endings
  4. LLM fallback with language hint for maximum accuracy
"""

from __future__ import annotations

import logging
import re
import unicodedata
from io import BytesIO
from pathlib import Path

import httpx
import asyncpg
import cv2
from PIL import Image
from anthropic import AsyncAnthropic

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer 1: Dictionary of common names with known gender
# ---------------------------------------------------------------------------

# Russian female names (nominative + common short forms)
_FEMALE_NAMES_RU = {
    "александра", "алёна", "алена", "алина", "алиса", "алла", "альбина",
    "анастасия", "настя", "ангелина", "анжела", "анна", "аня",
    "валентина", "валерия", "лера", "варвара", "вера", "вероника", "виктория", "вика",
    "галина", "дарья", "даша", "диана", "евгения", "женя",
    "екатерина", "катя", "елена", "лена", "елизавета", "лиза",
    "жанна", "злата", "зоя", "инна", "ирина", "ира",
    "карина", "кира", "кристина", "ксения", "ксюша",
    "лариса", "лидия", "лилия", "любовь", "люба", "людмила", "люда",
    "маргарита", "рита", "марина", "мария", "маша",
    "надежда", "надя", "наталья", "наталия", "наташа",
    "нина", "оксана", "олеся", "ольга", "оля",
    "полина", "регина", "роза", "светлана", "света",
    "снежана", "софья", "софия", "соня",
    "тамара", "татьяна", "таня", "ульяна",
    "элина", "эльвира", "юлия", "юля", "яна", "асель",
}

# Russian male names (nominative + common short forms)
_MALE_NAMES_RU = {
    "александр", "саша", "алексей", "лёша", "леша", "анатолий",
    "андрей", "антон", "аркадий", "артём", "артем", "артур",
    "богдан", "борис", "вадим", "валентин", "валерий",
    "василий", "виктор", "виталий", "владимир", "вова", "владислав", "влад",
    "вячеслав", "геннадий", "георгий", "глеб", "григорий",
    "даниил", "данил", "денис", "дмитрий", "дима",
    "евгений", "егор", "иван", "ваня", "игорь",
    "илья", "кирилл", "константин", "костя",
    "леонид", "максим", "макс", "марк", "матвей", "михаил", "миша",
    "никита", "николай", "коля", "олег",
    "павел", "паша", "пётр", "петр", "роман", "рома",
    "руслан", "сергей", "серёжа", "сережа",
    "станислав", "стас", "степан", "тимофей", "тимур",
    "фёдор", "федор", "филипп", "эдуард", "юрий", "юра", "ярослав",
}

# Common international names (covers English / European users on Phangan)
_FEMALE_NAMES_INT = {
    "anna", "maria", "julia", "natalia", "natalya", "natasha", "nina",
    "olga", "elena", "ekaterina", "dasha", "polina", "anastasia",
    "helen", "diana", "victoria", "marina", "sophia", "sofia",
    "alice", "emma", "olivia", "emily", "sarah", "jessica",
    "jennifer", "ashley", "amanda", "rachel", "megan", "lisa",
    "michelle", "laura", "stephanie", "nicole",
}

_MALE_NAMES_INT = {
    "alex", "alexander", "alexey", "sergei", "dmitry", "nikolai",
    "roman", "boris", "igor", "anton", "leon", "leo",
    "mark", "max", "maksim", "jacob", "james", "john", "robert",
    "michael", "david", "daniel", "matthew", "andrew", "joseph",
    "william", "richard", "thomas", "christopher", "brian", "kevin",
    "nick", "peter", "paul", "george", "denis", "dinar",
    "fedor", "jaroslav", "konstantin", "ruslan", "yuri", "danny",
}


def _lookup_dictionary(name: str) -> str | None:
    """Layer 1: Fast dictionary lookup. Returns 'male'/'female' or None."""
    low = name.strip().lower()
    # Try Russian sets first
    if low in _FEMALE_NAMES_RU:
        return "female"
    if low in _MALE_NAMES_RU:
        return "male"
    # International sets
    if low in _FEMALE_NAMES_INT:
        return "female"
    if low in _MALE_NAMES_INT:
        return "male"
    return None


# ---------------------------------------------------------------------------
# Layer 2: Emoji / non-letter validation
# ---------------------------------------------------------------------------

_LETTER_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ]")


def _has_letters(name: str) -> bool:
    """Returns True if the name contains at least one letter (Latin or Cyrillic)."""
    return bool(_LETTER_RE.search(name))


# ---------------------------------------------------------------------------
# Layer 3: Morphological analysis for Russian names
# ---------------------------------------------------------------------------

# Feminine endings (ordered by specificity, longest first)
_FEMALE_SUFFIXES = (
    "ия",   # Мария, Евгения, Наталия, Лилия
    "ья",   # Наталья, Дарья, Софья, Ульяна
    "на",   # Алёна, Елена, Марина, Ирина, Яна
    "ла",   # Алла
    "та",   # Рита, Злата, Света
    "да",   # Надя, Люда
    "ра",   # Вера, Тамара, Лера, Кира
    "за",   # Роза, Лиза, Элиза
    "са",   # Алиса, Лариса, Анфиса
    "ка",   # Вика, Анжелика
    "ша",   # Даша, Маша, Наташа, Ксюша
    "жа",   # Надежда (short: Надя, but "жа" ending)
    "га",   # Ольга
    "ва",   # Ева
    "ня",   # Соня, Таня, Аня, Женя (ambiguous but more often female)
    "ля",   # Юля, Оля
    "ся",   # Ася
    "а",    # generic -а ending (feminine in Russian)
    "я",    # generic -я ending (feminine in Russian)
)

# Masculine endings
_MALE_SUFFIXES = (
    "ей",   # Сергей, Алексей, Андрей
    "ий",   # Дмитрий, Виталий, Григорий, Юрий
    "ай",   # Николай
    "ой",   # (rare)
    "ёр",   # Фёдор
    "ор",   # Фёдор (ё→о variation)
    "ан",   # Иван, Руслан, Богдан, Роман
    "он",   # Антон, Семён
    "ён",   # Семён
    "им",   # Вадим, Максим
    "ис",   # Борис, Денис
    "ит",   # Никита (exception, but male)
    "ёб",   # Глеб
    "еб",   # Глеб (ё→е)
    "ур",   # Артур, Тимур
    "рк",   # Марк
    "ил",   # Даниил, Кирилл, Михаил
    "ёг",   # Олег
    "ег",   # Олег (ё→е)
    "ав",   # Вячеслав, Ярослав, Станислав
)


def _guess_by_morphology(name: str) -> str | None:
    """
    Layer 3: Morphological heuristic for Cyrillic names.
    Returns 'male'/'female' or None if name is not Cyrillic or ambiguous.
    """
    # Only apply to names that look Cyrillic
    if not re.search(r"[а-яА-ЯёЁ]", name):
        return None

    low = name.strip().lower()
    # Remove common decorations: emojis, @mentions, etc.
    low = re.sub(r"@\S+", "", low).strip()
    # Take the first word (actual name, not surname/nickname suffix)
    parts = low.split()
    if not parts:
        return None
    first = parts[0]

    if len(first) < 2:
        return None

    # Check feminine suffixes (longer first = more specific)
    for suffix in _FEMALE_SUFFIXES:
        if first.endswith(suffix):
            return "female"

    # Check masculine suffixes
    for suffix in _MALE_SUFFIXES:
        if first.endswith(suffix):
            return "male"

    # Consonant ending without specific suffix → likely male in Russian
    if re.match(r"[а-яё]", first[-1]) and first[-1] not in "аеёиоуыэюя":
        return "male"

    return None


# ---------------------------------------------------------------------------
# Layer 4: LLM fallback with language hint
# ---------------------------------------------------------------------------

async def _detect_gender_llm(first_name: str, language: str = "en") -> str:
    """Layer 4: LLM-based detection with language context for better accuracy."""
    settings = get_settings()
    if not settings.KIMI_CODE_API_KEY:
        logger.warning("KIMI_CODE_API_KEY not set. Defaulting gender to male.")
        return "male"

    lang_hint = "Russian" if language == "ru" else "English"

    try:
        client = AsyncAnthropic(
            api_key=settings.KIMI_CODE_API_KEY,
            base_url="https://api.kimi.com/coding/",
            default_headers={"User-Agent": "ClaudeCode/1.0"}
        )
        prompt = (
            f"The user's Telegram language is {lang_hint}. "
            f"Determine the most likely gender for the name '{first_name}'. "
            f"Reply strictly with either 'male' or 'female'."
        )

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
        logger.error("Gender detection LLM failed: %s", e)
        return "male"


# ---------------------------------------------------------------------------
# Public API: Cascading gender detection
# ---------------------------------------------------------------------------

async def detect_gender(first_name: str, language: str = "en") -> str:
    """
    Cascading gender detection:
      1. Dictionary lookup (instant, free, ~90% coverage for RU)
      2. Emoji/non-letter check → "unknown"
      3. Morphological analysis of Russian endings (instant, free)
      4. LLM fallback with language hint (1-2 sec, API call)
    """
    # Extract first word from compound names like "Богдан Тай"
    clean_name = first_name.strip().split()[0] if first_name.strip() else first_name

    # Layer 1: Dictionary
    result = _lookup_dictionary(clean_name)
    if result:
        logger.info("Gender for '%s' resolved via dictionary: %s", first_name, result)
        return result

    # Layer 2: No letters → unknown
    if not _has_letters(first_name):
        logger.info("Gender for '%s' is unknown (no letters in name)", first_name)
        return "unknown"

    # Layer 3: Morphological analysis (Cyrillic names)
    result = _guess_by_morphology(clean_name)
    if result:
        logger.info("Gender for '%s' resolved via morphology: %s", first_name, result)
        return result

    # Layer 4: LLM with language hint
    result = await _detect_gender_llm(first_name, language)
    logger.info("Gender for '%s' resolved via LLM: %s", first_name, result)
    return result


async def process_gender_background(
    pool: asyncpg.Pool,
    telegram_id: int,
    first_name: str,
    language: str = "en",
) -> None:
    """Background task for cascading gender detection."""
    logger.info("Starting gender worker for telegram_id=%s", telegram_id)
    # Cascading detection
    gender = await detect_gender(first_name, language)

    # DB Update
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

                # OpenCV Face Detection Pipeline
                from io import BytesIO
                image = Image.open(BytesIO(image_bytes))
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                import numpy as np
                import cv2
                img_rgb = np.array(image)
                img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

                # Use OpenCV's built-in Haar Cascade instead of broken MediaPipe 0.10.x solutions on Ubuntu
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                faces = face_cascade.detectMultiScale(img_gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))

                if len(faces) > 0:
                    is_aesthetic = True
                    logger.info("Face detected for %s via OpenCV: aesthetic=%s", telegram_id, is_aesthetic)

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
