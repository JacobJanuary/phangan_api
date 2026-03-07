import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the project root to sys.path to resolve imports properly
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Translation payload for English
EN_PAYLOAD = {
  "fake_loader": [
    "🕵️‍♀️ Scanning local private chats...",
    "🗑️ Filtering out spam and scams...",
    "✨ Calibrating your personal radar..."
  ],
  "gender_fallback": {
    "title": "Who are we finding a vibe for tonight?",
    "btn_male": "🧔🏻‍♂️ Guys", 
    "btn_female": "👩🏻🦰 Girls"
  },
  "ice_breaker": {
    "morning": {
      "greeting": "Good morning, {name} ☕️",
      "subtitle": "The island is waking up.",
      "buttons": [
        { "id": "yoga", "label": "🧘‍♀️ Restore HP" },
        { "id": "business", "label": "💻 Laptop & Focus" },
        { "id": "party", "label": "🪩 Day Party" },
        { "id": "all", "label": "🌴 Island Pulse" }
      ]
    },
    "day": {
      "greeting": "Golden hour, {name} 🌴",
      "subtitle": "Sunset plans?",
      "buttons": [
        { "id": "sunset", "label": "🌅 Catch Sunset" },
        { "id": "games", "label": "🏐 Games & Tribe" },
        { "id": "party", "label": "🚀 Night Plans" },
        { "id": "all", "label": "🌴 Island Pulse" }
      ]
    },
    "evening": {
      "greeting": "Time to shine, {name} 🪩",
      "subtitle": "Radars are glowing red.",
      "buttons": [
        { "id": "party", "label": "🔥 Into the epicenter" },
        { "id": "chill", "label": "🤫 Secret Chill" },
        { "id": "tomorrow", "label": "📅 Staying in. Tomorrow?" },
        { "id": "all", "label": "🌴 Island Pulse" }
      ]
    }
  }
}

# Translation payload for Russian
RU_PAYLOAD = {
  "fake_loader": [
    "🕵️‍♀️ Сканируем закрытые чаты Пангана...",
    "🗑️ Отсеиваем спам и скам...",
    "✨ Калибруем твой персональный радар..."
  ],
  "gender_fallback": {
    "title": "Для кого ищем компанию на вечер?",
    "btn_male": "🧔🏻‍♂️ Парни", 
    "btn_female": "👩🏻🦰 Девушки"
  },
  "ice_breaker": {
    "morning": {
      "greeting": "Доброе утро, {name} ☕️",
      "subtitle": "Остров просыпается. Какой вайб?",
      "buttons": [
        { "id": "yoga", "label": "🧘‍♀️ Восстановить ХП" },
        { "id": "business", "label": "💻 Лэптоп и Фокус" },
        { "id": "party", "label": "🪩 Дневная туса" },
        { "id": "all", "label": "🌴 Чем дышит остров" }
      ]
    },
    "day": {
      "greeting": "Экватор дня, {name} 🌴",
      "subtitle": "Куда едем на закат?",
      "buttons": [
        { "id": "sunset", "label": "🌅 Поймать закат" },
        { "id": "games", "label": "🏐 Свои люди и Игры" },
        { "id": "party", "label": "🚀 Планы на ночь" },
        { "id": "all", "label": "🌴 Чем дышит остров" }
      ]
    },
    "evening": {
      "greeting": "Время сиять, {name} 🪩",
      "subtitle": "Радары горят красным.",
      "buttons": [
        { "id": "party", "label": "🔥 В эпицентр" },
        { "id": "chill", "label": "🤫 Камерный чилл" },
        { "id": "tomorrow", "label": "📅 Я дома. Что завтра?" },
        { "id": "all", "label": "🌴 Чем дышит остров" }
      ]
    }
  }
}

async def seed_translations() -> None:
    settings = get_settings()
    logger.info("Connecting to database...")
    
    try:
        conn = await asyncpg.connect(
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            host=settings.DB_HOST,
            port=settings.DB_PORT
        )
        
        logger.info("Ensuring ui_translations table exists...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ui_translations (
                lang_code VARCHAR(5) PRIMARY KEY,
                onboarding JSONB NOT NULL
            );
        """)
        
        logger.info("Upserting English (en) translations...")
        await conn.execute(
            """
            INSERT INTO ui_translations (lang_code, onboarding) 
            VALUES ($1, $2::jsonb)
            ON CONFLICT (lang_code) 
            DO UPDATE SET onboarding = EXCLUDED.onboarding;
            """,
            "en",
            json.dumps(EN_PAYLOAD)
        )
        
        logger.info("Upserting Russian (ru) translations...")
        await conn.execute(
            """
            INSERT INTO ui_translations (lang_code, onboarding) 
            VALUES ($1, $2::jsonb)
            ON CONFLICT (lang_code) 
            DO UPDATE SET onboarding = EXCLUDED.onboarding;
            """,
            "ru",
            json.dumps(RU_PAYLOAD)
        )
        
        logger.info("Seed successful: ui_translations table populated.")
        
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
    finally:
        if 'conn' in locals() and conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_translations())
