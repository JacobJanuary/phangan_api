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
    # ═══════════════════════════════════════════════════════════════════════
    # 1. welcome (9 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("welcome", "tag_label",              "Твой путеводитель",                   "Your guide"),
    ("welcome", "headline_line1",         "Поймай",                              "Find your"),
    ("welcome", "headline_gradient_line2","свой вайб.",                           "vibe."),
    ("welcome", "subtitle",               "От утренней випассаны до секретных рейвов. Все события острова в одном месте.", "From morning dharma to secret raves. All island events in one place."),
    ("welcome", "feature1_title",         "Идеальный мэтч",                      "Perfect match"),
    ("welcome", "feature1_desc",          "Умный алгоритм покажет ивенты под твоё настроение.", "Forget the chat chaos. Smart algorithm shows events that fit your mood."),
    ("welcome", "feature2_title",         "Всё на радаре",                        "Everything on radar"),
    ("welcome", "feature2_desc",          "Интерактивная карта острова с маршрутами в один клик.", "Interactive island map with one-click navigation."),
    ("welcome", "btn_start",              "Погнали",                             "Let's go"),

    # ═══════════════════════════════════════════════════════════════════════
    # 2. welcome_back (2 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("welcome_back", "greeting",          "С возвращением, {name} 🪩",            "Welcome back, {name} 🪩"),
    ("welcome_back", "subtitle",          "Радар откалиброван ⚡️",               "Radar calibrated ⚡️"),

    # ═══════════════════════════════════════════════════════════════════════
    # 3. radar (15 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("radar", "location_label",           "Koh Phangan",                          "Koh Phangan"),
    ("radar", "filter_all_days",          "Все дни",                             "All days"),
    ("radar", "filter_today",             "Сегодня",                             "Today"),
    ("radar", "filter_tomorrow",          "Завтра",                              "Tomorrow"),
    ("radar", "filter_all_vibes",         "Все вайбы",                           "All vibes"),
    ("radar", "filter_all",               "Всё",                                 "All"),
    ("radar", "filter_sport",             "Актив",                               "Active"),
    ("radar", "filter_chill",             "Чилл",                                "Chill"),
    ("radar", "filter_party",             "Тусовки",                             "Party"),
    ("radar", "filter_edu",               "Развитие",                            "Growth"),
    ("radar", "filter_biz",               "Нетворк",                             "Network"),
    ("radar", "empty_title",              "Ничего не найдено 🌊",                "Nothing found 🌊"),
    ("radar", "empty_subtitle",           "Отдали карту или сдвиньте",            "Zoom out or pan around"),
    ("radar", "error_title",              "Mapbox не подключен",                  "Mapbox not connected"),
    ("radar", "error_desc",               "Вставь свой API-ключ...",              "Insert your API key (MAPBOX_TOKEN) in .env to load the map."),

    # ═══════════════════════════════════════════════════════════════════════
    # 4. swipe_feed (23 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("swipe_feed", "filter_all",          "Все",                                 "All"),
    ("swipe_feed", "filter_party",        "Тусовки",                             "Party"),
    ("swipe_feed", "filter_chill",        "Чилл",                                "Chill"),
    ("swipe_feed", "empty_title",         "Событий не найдено",                  "No events found"),
    ("swipe_feed", "empty_subtitle",      "Попробуй другой фильтр",              "Try a different filter"),
    ("swipe_feed", "onboarding_title",    "Выбирай свой вайб",                   "Choose your vibe"),
    ("swipe_feed", "onboarding_subtitle", "Свайпай карточки, чтобы собрать идеальный план.", "Swipe cards to build the perfect evening plan."),
    ("swipe_feed", "onboarding_pass",     "ПАСС",                                "PASS"),
    ("swipe_feed", "onboarding_save",     "В РАДАР",                             "TO RADAR"),
    ("swipe_feed", "onboarding_btn",      "Погнали 🔥",                          "Let's go 🔥"),
    ("swipe_feed", "onboarding_hint",     "Или тапни в любом месте",              "Or tap anywhere"),
    ("swipe_feed", "all_seen_title",      "Вы всё посмотрели!",                  "You've seen everything!"),
    ("swipe_feed", "all_seen_hint",       "То, что зацепило — в Мой Вайб. Мы сканируем чаты острова 24/7 — новые мероприятия появляются каждые ~20 минут!", "What caught your eye is in My Vibe. We scan island chats 24/7 — new events appear every ~20 min!"),
    ("swipe_feed", "checking",            "Проверяем...",                         "Checking..."),
    ("swipe_feed", "found_new",           "Нашли +{n}!",                          "Found +{n}!"),
    ("swipe_feed", "nothing_new",         "Пока ничего нового",                   "Nothing new yet"),
    ("swipe_feed", "refresh_feed",        "Обновить ленту",                       "Refresh feed"),
    ("swipe_feed", "unit_min",            "мин",                                  "min"),
    ("swipe_feed", "unit_km",             "км",                                   "km"),
    ("swipe_feed", "going",               "идут",                                 "going"),
    ("swipe_feed", "stamp_save",          "В радар",                              "To Radar"),
    ("swipe_feed", "stamp_pass",          "Пасс",                                 "Pass"),
    ("swipe_feed", "share_text",          "🔥 Го со мной на {title}!\n📍 {location} | 🗓 {date} • {time}\n\n👇 Жми, чтобы посмотреть...", "🔥 Join me at {title}!\n📍 {location} | 🗓 {date} • {time}\n\n👇 Tap to see the line-up..."),

    # ═══════════════════════════════════════════════════════════════════════
    # 5. my_vibe (6 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("my_vibe", "title",                  "Мой Вайб",                            "My Vibe"),
    ("my_vibe", "empty_subtitle",         "Расписание пустое. Свайпни вправо, чтобы добавить события.", "Your schedule is empty. Swipe right to collect events."),
    ("my_vibe", "count_subtitle",         "{count} событий запланировано.",        "{count} events planned."),
    ("my_vibe", "empty_state_label",      "Расписание чистое",                   "Schedule is clear"),
    ("my_vibe", "event_finished",         "СОБЫТИЕ ЗАВЕРШЕНО",                   "EVENT ENDED"),
    ("my_vibe", "pilot_subtitle",         "AI составит идеальный план дня",       "AI will create the perfect day plan"),

    # ═══════════════════════════════════════════════════════════════════════
    # 6. event_details (10 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("event_details", "label_where",      "Где",                                 "Where"),
    ("event_details", "label_when",       "Когда",                               "When"),
    ("event_details", "label_who",        "Кто идёт",                            "Who's going"),
    ("event_details", "label_on_radar",   "{count} на радаре",                   "{count} on radar"),
    ("event_details", "btn_route",        "Маршрут",                             "Route"),
    ("event_details", "section_about",    "О событии",                           "About"),
    ("event_details", "swipe_hint",       "Свайпни вниз, чтобы закрыть",         "Swipe down to close"),
    ("event_details", "secret_list_title","Секретный список",                     "Secret list"),
    ("event_details", "secret_list_desc", "Присоединись к событию, чтобы увидеть, кто будет.", "Join the event to see which contacts will be there."),
    ("event_details", "secret_list_badge","Скоро",                               "Soon"),

    # ═══════════════════════════════════════════════════════════════════════
    # 7. vibe_pilot (35 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("vibe_pilot", "tab_today",           "Сегодня",                              "Today"),
    ("vibe_pilot", "tab_tomorrow",        "Завтра",                               "Tomorrow"),
    ("vibe_pilot", "loading_hint_1",      "Анализируем события...",               "Analyzing events..."),
    ("vibe_pilot", "loading_hint_2",      "Оптимизируем маршрут...",              "Optimizing route..."),
    ("vibe_pilot", "loading_hint_3",      "Подбираем расписание...",              "Building schedule..."),
    ("vibe_pilot", "loading_hint_4",      "Рассчитываем время в пути...",         "Calculating travel time..."),
    ("vibe_pilot", "loading_hint_5",      "Составляем идеальный план...",         "Creating the perfect plan..."),
    ("vibe_pilot", "btn_map",             "Карта",                                "Map"),
    ("vibe_pilot", "share_friend",        "Поделиться с другом",                  "Share with friend"),
    ("vibe_pilot", "share_generating",    "Генерируем карточку...",               "Generating card..."),
    ("vibe_pilot", "share_sent_story",    "Отправлено в Story!",                  "Sent to Story!"),
    ("vibe_pilot", "share_downloaded",    "Скачано!",                             "Downloaded!"),
    ("vibe_pilot", "share_copied",        "Скопировано!",                         "Copied!"),
    ("vibe_pilot", "share_sent",          "Отправлено!",                          "Sent!"),
    ("vibe_pilot", "share_plan_name",     "Создай свой план",                     "Create your plan"),
    ("vibe_pilot", "canvas_watermark",    "Made with AI · VibeRadar 🧭",          "Made with AI · VibeRadar 🧭"),
    ("vibe_pilot", "price_free",          "БЕСПЛАТНО",                            "FREE"),
    ("vibe_pilot", "travel_from_you",     "от вас",                               "from you"),
    ("vibe_pilot", "loading_title",       "Планируем идеальный день",             "Planning the perfect day"),
    ("vibe_pilot", "error_title",         "Не удалось создать план",              "Could not create plan"),
    ("vibe_pilot", "error_subtitle",      "AI-сервис временно недоступен",         "AI service is temporarily unavailable"),
    ("vibe_pilot", "error_retry",         "Попробовать снова",                    "Try again"),
    ("vibe_pilot", "zero_title",          "Пилоту нужны координаты",              "Pilot needs coordinates"),
    ("vibe_pilot", "zero_subtitle",       "Сохрани несколько событий в ленте, и AI создаст идеальный план дня.", "Save a few events in the feed, and AI will create the perfect day plan for you."),
    ("vibe_pilot", "zero_btn",            "Найти события 🔥",                     "Find events 🔥"),
    ("vibe_pilot", "empty_title",         "План пуст",                            "Plan is empty"),
    ("vibe_pilot", "empty_btn",           "Листать ленту",                        "Browse feed"),
    ("vibe_pilot", "force_swipe_btn",     "Свайпать события",                     "Swipe events"),
    ("vibe_pilot", "few_events_title",    "Мало сохраненных событий ({count})",    "Few saved events ({count})"),
    ("vibe_pilot", "few_events_desc",     "ИИ еще не до конца изучил ваши вкусы...", "AI hasn't fully learned your tastes yet..."),
    ("vibe_pilot", "unit_events",         "событий",                              "events"),
    ("vibe_pilot", "unit_km",             "км",                                   "km"),
    ("vibe_pilot", "map_title",           "Маршрут Дня",                          "Day Route"),
    ("vibe_pilot", "btn_navigate",        "Навигатор",                            "Navigate"),
    ("vibe_pilot", "btn_details",         "Детали",                               "Details"),
    ("vibe_pilot", "share_cta",           "👇 Открой VibeRadar чтобы увидеть детали:", "👇 Open VibeRadar to see details:"),

    # ═══════════════════════════════════════════════════════════════════════
    # 8. live_tracker (5 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("live_tracker", "label_now",         "СЕЙЧАС",                               "NOW"),
    ("live_tracker", "label_next",        "ДАЛЕЕ",                                "NEXT"),
    ("live_tracker", "day_completed",     "День завершён",                        "Day completed"),
    ("live_tracker", "plan_tomorrow",     "Завтра →",                             "Tomorrow →"),
    ("live_tracker", "in_time",           "через {time}",                         "in {time}"),

    # ═══════════════════════════════════════════════════════════════════════
    # 9. edit_event (18 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("edit_event", "title",               "Редактирование",                       "Edit Event"),
    ("edit_event", "btn_change_photo",    "Сменить фото",                         "Change photo"),
    ("edit_event", "btn_changed_photo",   "Сменить",                              "Change"),
    ("edit_event", "label_title",         "Название",                             "Title"),
    ("edit_event", "label_summary",       "Краткое описание",                     "Summary"),
    ("edit_event", "label_description",   "Описание",                             "Description"),
    ("edit_event", "label_date",          "Дата",                                 "Date"),
    ("edit_event", "label_time",          "Время",                                "Time"),
    ("edit_event", "placeholder_title",   "Название события на {lang}",            "Event title in {lang}"),
    ("edit_event", "placeholder_summary", "Краткое описание на {lang}",            "Short summary in {lang}"),
    ("edit_event", "placeholder_description", "Детали события (2-4 предложения) на {lang}", "Event details (2-4 sentences) in {lang}"),
    ("edit_event", "btn_save",            "Сохранить изменения",                   "Save Changes"),
    ("edit_event", "btn_saving",          "Сохраняем...",                          "Saving Changes..."),
    ("edit_event", "btn_uploading",       "Загружаем фото...",                     "Uploading Image..."),
    ("edit_event", "btn_delete",          "Удалить событие",                       "Delete Event"),
    ("edit_event", "btn_deleting",        "Удаляем...",                            "Deleting..."),
    ("edit_event", "confirm_delete",      "Удалить это событие? Действие нельзя отменить.", "Delete this event? This action cannot be undone."),
    ("edit_event", "file_too_large",      "Файл слишком большой (макс 5 МБ)",      "File too large (max 5 MB)"),

    # ═══════════════════════════════════════════════════════════════════════
    # 10. questionnaire (38 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("questionnaire", "greeting",              "ПРИВЕТ, {NAME} 👋",               "HI, {NAME} 👋"),
    ("questionnaire", "greeting_fallback",     "НАСТРОЙКА РАДАРА",                 "RADAR SETUP"),
    ("questionnaire", "gender_girl",           "Девушка",                          "Girl"),
    ("questionnaire", "gender_boy",            "Парень",                           "Guy"),
    ("questionnaire", "gender_heading",        "Уточни\nсвой пол",                "Specify\nyour gender"),
    ("questionnaire", "gender_desc",           "На острове проходят закрытые женские круги и мужские практики...", "The island hosts women-only circles and men-only practices..."),
    ("questionnaire", "top_label",             "Топ",                              "Top"),
    ("questionnaire", "show_all",              "Удивите меня (Показать всё)",       "Surprise me (Show all)"),
    ("questionnaire", "question_morning",      "Как начнём\nутро?",                "How shall we\nstart the day?"),
    ("questionnaire", "question_afternoon",    "Во что\nнырнём?",                  "What shall\nwe dive into?"),
    ("questionnaire", "question_evening",      "Куда\nна закат?",                  "Where to\nfor sunset?"),
    ("questionnaire", "question_night",        "Ищешь\nночной вайб?",              "Looking for\nnight vibes?"),
    ("questionnaire", "greet_morning_1",       "Доброе утро{name} ☕️",             "Good morning{name} ☕️"),
    ("questionnaire", "greet_morning_2",       "Просыпайся{name} ☀️",              "Rise and shine{name} ☀️"),
    ("questionnaire", "greet_morning_3",       "Идеальное утро{name} 🌊",           "Perfect morning{name} 🌊"),
    ("questionnaire", "greet_morning_4",       "{prefix}ВРЕМЯ ДЛЯ КОФЕ 🥥",        "{prefix}COFFEE TIME 🥥"),
    ("questionnaire", "greet_afternoon_1",     "Экватор дня{name} 🌴",              "Midday vibes{name} 🌴"),
    ("questionnaire", "greet_afternoon_2",     "Лови момент{name} 🛵",              "Seize the moment{name} 🛵"),
    ("questionnaire", "greet_afternoon_3",     "Отличный день{name} 🥥",            "Great day{name} 🥥"),
    ("questionnaire", "greet_afternoon_4",     "{prefix}СОЛНЦЕ В ЗЕНИТЕ ☀️",        "{prefix}SUN AT ITS PEAK ☀️"),
    ("questionnaire", "greet_evening_1",       "Горит закат{name} 🌅",              "Sunset glowing{name} 🌅"),
    ("questionnaire", "greet_evening_2",       "Время магии{name} ✨",               "Magic hour{name} ✨"),
    ("questionnaire", "greet_evening_3",       "Золотой час{name} 🍹",              "Golden hour{name} 🍹"),
    ("questionnaire", "greet_evening_4",       "{prefix}ПРОВОЖАЕМ СОЛНЦЕ 🌴",       "{prefix}CHASING THE SUN 🌴"),
    ("questionnaire", "greet_night_1",         "Остров не спит{name} 🌙",           "Island never sleeps{name} 🌙"),
    ("questionnaire", "greet_night_2",         "Твоя ночь{name} 🪩",                "Your night{name} 🪩"),
    ("questionnaire", "greet_night_3",         "Готов к отрыву{name}? 🔥",           "Ready to party{name}? 🔥"),
    ("questionnaire", "greet_night_4",         "{prefix}НОЧНЫЕ ВИБРАЦИИ 🌌",        "{prefix}NIGHT VIBES 🌌"),
    ("questionnaire", "cat_sport_title",       "Зарядись\nэнергией",                "Get\nactive"),
    ("questionnaire", "cat_sport_desc",        "Йога, танцы, спорт",               "Yoga, dance, sports"),
    ("questionnaire", "cat_chill_title",       "Найди\nдзен",                      "Find\nzen"),
    ("questionnaire", "cat_chill_desc",        "Закаты, хилинг, спа",              "Sunsets, healing, spa"),
    ("questionnaire", "cat_edu_title",         "Узнай\nновое",                     "Learn\nsomething"),
    ("questionnaire", "cat_edu_desc",          "Воркшопы, лекции",                 "Workshops, lectures"),
    ("questionnaire", "cat_party_title",       "Оторвись",                         "Let\nloose"),
    ("questionnaire", "cat_party_desc",        "Рейвы, музыка, бары",              "Raves, music, bars"),
    ("questionnaire", "cat_biz_title",         "Полезные связи",                   "Useful connections"),
    ("questionnaire", "cat_biz_desc",          "IT, крипто, бизнес",               "IT, crypto, business"),

    # ═══════════════════════════════════════════════════════════════════════
    # 11. categories (6 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("categories", "filter_all",               "Все",                              "All"),
    ("categories", "filter_sport",             "Спорт",                            "Sport"),
    ("categories", "filter_chill",             "Чилл",                             "Chill"),
    ("categories", "filter_education",         "Развитие",                         "Education"),
    ("categories", "filter_party",             "Тусовки",                          "Party"),
    ("categories", "filter_business",          "Нетворк",                          "Network"),

    # ═══════════════════════════════════════════════════════════════════════
    # 12. fake_loader (3 keys — onboarding loader steps)
    # ═══════════════════════════════════════════════════════════════════════
    ("fake_loader", "step_0",             "🕵️‍♀️ Сканируем местные вайбы...",       "🕵️‍♀️ Scanning local vibes..."),
    ("fake_loader", "step_1",             "🗑️ Фильтруем шум...",                  "🗑️ Filtering out the noise..."),
    ("fake_loader", "step_2",             "✨ Калибруем радар...",                  "✨ Calibrating your radar..."),

    # ═══════════════════════════════════════════════════════════════════════
    # 13. gender_fallback (3 keys)
    # ═══════════════════════════════════════════════════════════════════════
    ("gender_fallback", "title",          "Кто ты?",                              "Who are you?"),
    ("gender_fallback", "btn_male",       "🧔 Мужчина",                           "🧔 Male"),
    ("gender_fallback", "btn_female",     "👩 Женщина",                           "👩 Female"),

    # ═══════════════════════════════════════════════════════════════════════
    # 14. ice_breaker (12 keys — 3 time slots × 4 keys each)
    # ═══════════════════════════════════════════════════════════════════════
    ("ice_breaker", "morning_greeting",   "Доброе утро, {name}! ☀️",              "Good morning, {name}! ☀️"),
    ("ice_breaker", "morning_subtitle",   "Какой план на сегодня?",               "What's the plan for today?"),
    ("ice_breaker", "morning_btn_0",      "🧘 Медленный старт",                   "🧘 Slow Start"),
    ("ice_breaker", "morning_btn_1",      "💼 Продуктивный день",                  "💼 Productive Day"),
    ("ice_breaker", "morning_btn_2",      "🔥 Сразу на максимум",                  "🔥 Go Hard Already"),
    ("ice_breaker", "day_greeting",       "Привет, {name}! 👋",                   "Hey, {name}! 👋"),
    ("ice_breaker", "day_subtitle",       "Какой вайб сейчас?",                   "What's the vibe right now?"),
    ("ice_breaker", "day_btn_0",          "🌴 Просто чиллю",                      "🌴 Just Chilling"),
    ("ice_breaker", "day_btn_1",          "💡 Нетворкинг",                        "💡 Networking"),
    ("ice_breaker", "day_btn_2",          "🎉 Готов тусить",                      "🎉 Ready to Party"),
    ("ice_breaker", "evening_greeting",   "Вечер, {name}! 🌙",                   "Evening, {name}! 🌙"),
    ("ice_breaker", "evening_subtitle",   "Как проведём вечер?",                  "How do you want tonight to go?"),
    ("ice_breaker", "evening_btn_0",      "🌊 Чилл-вайб",                        "🌊 Chill Vibes"),
    ("ice_breaker", "evening_btn_1",      "🍷 Социальный вечер",                  "🍷 Social Night"),
    ("ice_breaker", "evening_btn_2",      "🔥 На полную",                         "🔥 Full Send"),
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
