"""Bot webhook business logic."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import fcntl

from core.config import Settings
from features.bot.client import TelegramBotClient
from features.bot.messages import WELCOME_TEXT_EN, WELCOME_TEXT_RU

logger = logging.getLogger(__name__)

_WEBHOOK_LOCK_ENV = "PHANGAN_API_WEBHOOK_LOCK_PATH"
_WEBHOOK_COOLDOWN_ENV = "PHANGAN_API_WEBHOOK_COOLDOWN_S"
_DEFAULT_WEBHOOK_COOLDOWN_S = 300.0


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
    webhook_url = f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}/api/bot/webhook"
    lock_path = _webhook_lock_path()
    cooldown_s = _webhook_cooldown_s()

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if not _try_lock(lock_file):
            logger.info(
                "Skipping Telegram webhook registration; another worker is handling it",
                extra={"lock_path": str(lock_path)},
            )
            return False

        try:
            if _recent_success(lock_file, webhook_url, cooldown_s):
                logger.info(
                    "Skipping Telegram webhook registration; recently registered",
                    extra={"url": webhook_url, "cooldown_s": cooldown_s},
                )
                return True

            service = BotService(settings=settings)
            ok = await service.register_webhook_url(settings.PUBLIC_API_BASE_URL)
            if ok:
                _record_success(lock_file, webhook_url)
            return ok
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _webhook_lock_path() -> Path:
    raw_path = os.getenv(_WEBHOOK_LOCK_ENV)
    if raw_path:
        return Path(raw_path)
    return Path(tempfile.gettempdir()) / "phangan_api_webhook_register.lock"


def _webhook_cooldown_s() -> float:
    raw_value = os.getenv(_WEBHOOK_COOLDOWN_ENV)
    if not raw_value:
        return _DEFAULT_WEBHOOK_COOLDOWN_S
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        logger.warning(
            "Invalid webhook cooldown; using default",
            extra={"env": _WEBHOOK_COOLDOWN_ENV, "value": raw_value},
        )
        return _DEFAULT_WEBHOOK_COOLDOWN_S


def _try_lock(lock_file: TextIO) -> bool:
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _recent_success(lock_file: TextIO, webhook_url: str, cooldown_s: float) -> bool:
    if cooldown_s <= 0:
        return False

    lock_file.seek(0)
    raw_state = lock_file.read().strip()
    if not raw_state:
        return False

    try:
        state = json.loads(raw_state)
    except json.JSONDecodeError:
        return False

    if state.get("webhook_url") != webhook_url:
        return False

    try:
        registered_at = float(state.get("registered_at", 0))
    except (TypeError, ValueError):
        return False

    return (time.time() - registered_at) < cooldown_s


def _record_success(lock_file: TextIO, webhook_url: str) -> None:
    lock_file.seek(0)
    lock_file.truncate()
    json.dump({"webhook_url": webhook_url, "registered_at": time.time()}, lock_file)
    lock_file.flush()
