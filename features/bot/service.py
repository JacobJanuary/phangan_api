"""Bot webhook business logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.config import Settings
from features.bot.client import TelegramBotClient
from features.bot.messages import WELCOME_TEXT_EN, WELCOME_TEXT_RU

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BotService:
    """Handles incoming Telegram updates and webhook registration."""

    settings: Settings

    @property
    def _client(self) -> TelegramBotClient:
        return TelegramBotClient(bot_token=self.settings.BOT_TOKEN)

    async def handle_update(self, update: dict) -> None:
        message = update.get("message") if isinstance(update, dict) else None
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        if chat_id is None:
            return

        text = (message.get("text") or "").strip()
        lang_raw = (message.get("from", {}).get("language_code") or "en")
        lang = lang_raw[:2].lower()

        if text.startswith("/start"):
            await self._send_welcome(chat_id, lang)

    async def _send_welcome(self, chat_id: int, lang: str) -> None:
        is_ru = lang == "ru"
        welcome = WELCOME_TEXT_RU if is_ru else WELCOME_TEXT_EN
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🌴 Открыть GoPhangan" if is_ru else "🌴 Open GoPhangan",
                        "web_app": {"url": self.settings.PUBLIC_MINIAPP_URL},
                    }
                ],
                [
                    {
                        "text": "📱 Добавить на домашний экран"
                        if is_ru
                        else "📱 Add to Home Screen",
                        "url": f"https://t.me/{self.settings.TELEGRAM_BOT_USERNAME}",
                    }
                ],
            ]
        }
        await self._client.call(
            "sendMessage",
            chat_id=chat_id,
            text=welcome,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    async def register_webhook_url(self, base_url: str) -> bool:
        webhook_url = f"{base_url.rstrip('/')}/api/bot/webhook"
        result = await self._client.call("setWebhook", url=webhook_url)
        ok = bool(result.get("ok"))
        if ok:
            logger.info("Telegram webhook registered", extra={"url": webhook_url})
        else:
            logger.error(
                "Failed to register Telegram webhook",
                extra={"url": webhook_url, "response": result},
            )
        return ok


async def register_webhook(settings: Settings) -> bool:
    """Module-level helper used by the application lifespan."""
    service = BotService(settings=settings)
    return await service.register_webhook_url(settings.PUBLIC_API_BASE_URL)
