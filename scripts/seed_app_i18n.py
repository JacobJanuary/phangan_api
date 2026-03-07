import asyncio
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# All translations: (screen, key, ru, en)
TRANSLATIONS = [
    # welcome
    ("welcome", "tag_label",              "Твой путеводитель",                   "Your guide"),
    ("welcome", "headline_line1",         "Поймай",                              "Find your"),
    ("welcome", "headline_gradient_line2","свой вайб.",                           "vibe."),
    ("welcome", "subtitle",               "От утренней випассаны до секретных рейвов. Все события острова в одном месте.", "From morning dharma to secret raves. All island events in one place."),
    ("welcome", "feature1_title",         "Идеальный мэтч",                      "Perfect match"),
    ("welcome", "feature1_desc",          "Умный алгоритм покажет ивенты под твоё настроение.", "Smart algorithm shows events that fit your mood."),
    ("welcome", "feature2_title",         "Всё на радаре",                        "Everything on radar"),
    ("welcome", "feature2_desc",          "Интерактивная карта острова с маршрутами в один клик.", "Interactive island map with one-click navigation."),
    ("welcome", "btn_start",              "Погнали",                             "Let's go"),

    # welcome_back
    ("welcome_back", "greeting",          "С возвращением, {name} 🪩",            "Welcome back, {name} 🪩"),
    ("welcome_back", "subtitle",          "Радар откалиброван ⚡️",               "Radar calibrated ⚡️"),

    # radar
    ("radar", "location_label",           "Остров Панган",                        "Koh Phangan"),
    ("radar", "filter_all_days",          "Все дни",                             "All days"),
    ("radar", "filter_today",             "Сегодня",                             "Today"),
    ("radar", "filter_tomorrow",          "Завтра",                              "Tomorrow"),
    ("radar", "filter_all_vibes",         "Все вайбы",                           "All vibes"),
    ("radar", "filter_party",             "Рейв",                                "Party"),
    ("radar", "filter_chill",             "Чилл",                                "Chill"),
    ("radar", "empty_title",              "Ничего не найдено 🌊",                "Nothing found 🌊"),
    ("radar", "empty_subtitle",           "Отдалите карту или сдвиньте её",       "Zoom out or pan around"),

    # swipe_feed
    ("swipe_feed", "filter_all",          "Всё",                                 "All"),
    ("swipe_feed", "filter_party",        "Рейв",                                "Party"),
    ("swipe_feed", "filter_chill",        "Чилл",                                "Chill"),
    ("swipe_feed", "empty_title",         "Тусовок не нашлось",                  "No events found"),
    ("swipe_feed", "empty_subtitle",      "Попробуй изменить фильтр",            "Try a different filter"),

    # my_vibe
    ("my_vibe", "title",                  "Мой Вайб",                            "My Vibe"),
    ("my_vibe", "empty_subtitle",         "Твой календарь пуст. Свайпай вправо, чтобы собирать тусовки.", "Your schedule is empty. Swipe right to collect events."),
    ("my_vibe", "count_subtitle",         "У тебя в планах {count} ивента.",      "You have {count} events planned."),
    ("my_vibe", "empty_state_label",      "Планы чисты",                         "Schedule is clear"),
    ("my_vibe", "event_finished",         "СОБЫТИЕ ЗАВЕРШЕНО",                   "EVENT ENDED"),

    # event_details
    ("event_details", "label_where",      "Где",                                 "Where"),
    ("event_details", "label_when",       "Когда",                               "When"),
    ("event_details", "label_who",        "Кто идет",                            "Who's going"),
    ("event_details", "label_on_radar",   "{count} на радаре",                   "{count} on radar"),
    ("event_details", "btn_route",        "Маршрут",                             "Route"),
    ("event_details", "section_about",    "О событии",                           "About"),
    ("event_details", "swipe_hint",       "Смахнуть вниз для возврата",          "Swipe down to close"),
    ("event_details", "secret_list_title","Секретный список",                     "Secret list"),
    ("event_details", "secret_list_desc", "Запишись на ивент, чтобы увидеть, кто из контактов будет там.", "Join the event to see which contacts will be there."),
    ("event_details", "secret_list_badge","Скоро",                               "Soon"),
]


async def seed_app_i18n() -> None:
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

        logger.info("Creating app_i18n table if not exists...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_i18n (
                id         SERIAL PRIMARY KEY,
                lang       VARCHAR(5)   NOT NULL,
                screen     VARCHAR(50)  NOT NULL,
                key        VARCHAR(100) NOT NULL,
                value      TEXT         NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(lang, screen, key)
            );
        """)

        logger.info("Seeding %d translation rows (ru + en)...", len(TRANSLATIONS))
        for screen, key, ru_val, en_val in TRANSLATIONS:
            # Upsert Russian
            await conn.execute(
                """
                INSERT INTO app_i18n (lang, screen, key, value)
                VALUES ('ru', $1, $2, $3)
                ON CONFLICT (lang, screen, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
                """,
                screen, key, ru_val
            )
            # Upsert English
            await conn.execute(
                """
                INSERT INTO app_i18n (lang, screen, key, value)
                VALUES ('en', $1, $2, $3)
                ON CONFLICT (lang, screen, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
                """,
                screen, key, en_val
            )

        count = await conn.fetchval("SELECT COUNT(*) FROM app_i18n")
        logger.info("Seed successful: app_i18n now has %d rows.", count)

    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        raise
    finally:
        if 'conn' in locals() and conn:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_app_i18n())
