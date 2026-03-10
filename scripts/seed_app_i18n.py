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

    # swipe_feed (existing + new keys)
    ("swipe_feed", "filter_all",          "Всё",                                 "All"),
    ("swipe_feed", "filter_party",        "Рейв",                                "Party"),
    ("swipe_feed", "filter_chill",        "Чилл",                                "Chill"),
    ("swipe_feed", "empty_title",         "Тусовок не нашлось",                  "No events found"),
    ("swipe_feed", "empty_subtitle",      "Попробуй изменить фильтр",            "Try a different filter"),
    ("swipe_feed", "all_seen_title",      "Ты всё просмотрел!",                  "You've seen everything!"),
    ("swipe_feed", "all_seen_hint",       "То что заинтересовало — ищи в Мой Вайб. Мы сканируем чаты острова 24/7 — новые мероприятия появляются каждые ~20 минут!", "What caught your eye is in My Vibe. We scan island chats 24/7 — new events appear every ~20 min!"),
    ("swipe_feed", "checking",            "Проверяем...",                         "Checking..."),
    ("swipe_feed", "found_new",           "Нашли +{n}!",                          "Found +{n}!"),
    ("swipe_feed", "nothing_new",         "Ничего нового пока",                   "Nothing new yet"),
    ("swipe_feed", "refresh_feed",        "Обновить ленту",                       "Refresh feed"),

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

    # vibe_pilot
    ("vibe_pilot", "tab_today",           "Сегодня",                              "Today"),
    ("vibe_pilot", "tab_tomorrow",        "Завтра",                               "Tomorrow"),
    ("vibe_pilot", "loading_hint_1",      "Анализируем события...",               "Analyzing events..."),
    ("vibe_pilot", "loading_hint_2",      "Оптимизируем маршрут...",              "Optimizing route..."),
    ("vibe_pilot", "loading_hint_3",      "Подбираем расписание...",              "Building schedule..."),
    ("vibe_pilot", "loading_hint_4",      "Рассчитываем время в пути...",         "Calculating travel time..."),
    ("vibe_pilot", "loading_hint_5",      "Составляем идеальный план...",         "Creating the perfect plan..."),
    ("vibe_pilot", "btn_map",             "Карта",                                "Map"),
    ("vibe_pilot", "share_friend",        "Отправить другу",                      "Share with friend"),
    ("vibe_pilot", "share_generating",    "Генерируем карточку...",               "Generating card..."),
    ("vibe_pilot", "share_sent_story",    "Отправлено в Story!",                  "Sent to Story!"),
    ("vibe_pilot", "share_downloaded",    "Скачано!",                             "Downloaded!"),
    ("vibe_pilot", "share_copied",        "Скопировано!",                         "Copied!"),
    ("vibe_pilot", "share_sent",          "Отправлено!",                          "Sent!"),
    ("vibe_pilot", "share_plan_name",     "Составить свой план",                  "Create your plan"),
    ("vibe_pilot", "canvas_watermark",    "Составлено AI · VibeRadar 🧭",         "Made with AI · VibeRadar 🧭"),
    ("vibe_pilot", "price_free",          "FREE",                                 "FREE"),
    ("vibe_pilot", "travel_from_you",     "от тебя",                              "from you"),

    # live_tracker
    ("live_tracker", "label_now",         "NOW",                                  "NOW"),
    ("live_tracker", "label_next",        "NEXT",                                 "NEXT"),
    ("live_tracker", "day_completed",     "День завершён",                        "Day completed"),
    ("live_tracker", "plan_tomorrow",     "Завтра →",                             "Tomorrow →"),

    # edit_event
    ("edit_event", "title",               "Редактирование",                       "Edit Event"),
    ("edit_event", "label_image",         "Фото события",                         "Event Image"),
    ("edit_event", "btn_change_photo",    "Заменить фото",                        "Change photo"),
    ("edit_event", "btn_changed_photo",   "Изменить",                             "Change"),
    ("edit_event", "label_title",         "Название",                             "Title"),
    ("edit_event", "label_summary",       "Краткое описание",                     "Summary"),
    ("edit_event", "label_description",   "Описание",                             "Description"),
    ("edit_event", "label_date",          "Дата",                                 "Date"),
    ("edit_event", "label_time",          "Время",                                "Time"),
    ("edit_event", "placeholder_title",   "Название на {lang}",                   "Event title in {lang}"),
    ("edit_event", "placeholder_summary", "Краткое описание на {lang}",           "Short summary in {lang}"),
    ("edit_event", "placeholder_description", "Описание (2-4 предложения) на {lang}", "Event details (2-4 sentences) in {lang}"),
    ("edit_event", "btn_save",            "Сохранить",                            "Save Changes"),
    ("edit_event", "btn_saving",          "Сохраняем...",                         "Saving Changes..."),
    ("edit_event", "btn_uploading",       "Загрузка фото...",                     "Uploading Image..."),
    ("edit_event", "btn_delete",          "Удалить событие",                      "Delete Event"),
    ("edit_event", "btn_deleting",        "Удаление...",                          "Deleting..."),
    ("edit_event", "confirm_delete",      "Удалить событие? Это действие нельзя отменить.", "Delete this event? This action cannot be undone."),
    ("edit_event", "file_too_large",      "Файл слишком большой (макс. 5 МБ)",    "File too large (max 5 MB)"),

    # questionnaire
    ("questionnaire", "greeting",              "ПРИВЕТ, {NAME} 👋",               "HI, {NAME} 👋"),
    ("questionnaire", "greeting_fallback",     "НАСТРОЙКА РАДАРА",                 "RADAR SETUP"),
    ("questionnaire", "gender_girl",           "Девушка",                          "Girl"),
    ("questionnaire", "gender_boy",            "Парень",                           "Guy"),
    ("questionnaire", "top_label",             "Топ",                              "Top"),
    ("questionnaire", "question_morning",      "Как начнем\nэтот день?",           "How shall we\nstart the day?"),
    ("questionnaire", "question_afternoon",    "Во что\nпогрузимся?",              "What shall\nwe dive into?"),
    ("questionnaire", "question_evening",      "Куда проводим\nсолнце?",           "Where to\nfor sunset?"),
    ("questionnaire", "question_night",        "Ищем вайб\nна ночь?",              "Looking for\nnight vibes?"),
    ("questionnaire", "cat_sport_title",       "Размять\nтело",                    "Get\nactive"),
    ("questionnaire", "cat_sport_desc",        "Йога, танцы, спорт",               "Yoga, dance, sports"),
    ("questionnaire", "cat_chill_title",       "Поймать\nдзен",                    "Find\nzen"),
    ("questionnaire", "cat_chill_desc",        "Сансеты, хилинг, спа",             "Sunsets, healing, spa"),
    ("questionnaire", "cat_edu_title",         "Узнать\nновое",                    "Learn\nsomething"),
    ("questionnaire", "cat_edu_desc",          "Мастер-классы, лекции",            "Workshops, lectures"),
    ("questionnaire", "cat_party_title",       "Уйти в\nотрыв",                   "Let\nloose"),
    ("questionnaire", "cat_party_desc",        "Рейвы, музыка, бары",              "Raves, music, bars"),
    ("questionnaire", "cat_biz_title",         "Полезные связи",                   "Useful connections"),
    ("questionnaire", "cat_biz_desc",          "IT, крипта, бизнес-завтраки",      "IT, crypto, business"),

    # categories
    ("categories", "filter_all",               "Всё",                              "All"),
    ("categories", "filter_sport",             "Актив",                            "Sport"),
    ("categories", "filter_chill",             "Чилл",                             "Chill"),
    ("categories", "filter_education",         "Развитие",                         "Education"),
    ("categories", "filter_party",             "Тусовки",                          "Party"),
    ("categories", "filter_business",          "Нетворк",                          "Network"),
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
