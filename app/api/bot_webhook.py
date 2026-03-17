"""
Telegram Bot Webhook – handles /start and other bot commands.

Lightweight handler using raw Telegram Bot API (no aiogram/python-telegram-bot).
Registered as a FastAPI route and wired to Telegram via setWebhook on startup.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bot"])

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# ── Helpers ──────────────────────────────────────────────────────────────

async def _tg(method: str, **kwargs: Any) -> dict:
    """Call Telegram Bot API method."""
    settings = get_settings()
    url = TELEGRAM_API.format(token=settings.BOT_TOKEN, method=method)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=kwargs)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram API error: %s %s", method, data)
        return data


WELCOME_TEXT_RU = (
    "🌴 <b>Добро пожаловать в GoPhangan!</b>\n"
    "\n"
    "Все события Ко Пангана в одном приложении:\n"
    "🎉 Вечеринки  🧘 Йога  🎵 Живая музыка  🍜 Фуд-маркеты\n"
    "\n"
    "🧭 <b>Vibe Pilot</b> — AI-планировщик составит идеальный маршрут на весь день.\n"
    "\n"
    '📌 <i>Совет: закрепи этот чат, чтобы не потерять афишу!</i>\n'
    "   Зажми чат → «Закрепить»"
)

WELCOME_TEXT_EN = (
    "🌴 <b>Welcome to GoPhangan!</b>\n"
    "\n"
    "Every event on Koh Phangan in one app:\n"
    "🎉 Parties  🧘 Yoga  🎵 Live Music  🍜 Food Markets\n"
    "\n"
    "🧭 <b>Vibe Pilot</b> — AI planner builds your perfect day route.\n"
    "\n"
    '📌 <i>Tip: pin this chat so you never lose the event guide!</i>\n'
    '   Long-press the chat → "Pin"'
)


# ── Webhook endpoint ─────────────────────────────────────────────────────

@router.post("/api/bot/webhook", include_in_schema=False)
async def bot_webhook(request: Request) -> Response:
    """Handle incoming Telegram updates."""
    try:
        update: dict = await request.json()
    except Exception:
        return Response(status_code=200)

    message = update.get("message")
    if not message:
        return Response(status_code=200)

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    lang = (message.get("from", {}).get("language_code") or "en")[:2]

    if text.startswith("/start"):
        welcome = WELCOME_TEXT_RU if lang == "ru" else WELCOME_TEXT_EN

        # Inline keyboard with "Open App" button
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🌴 Открыть GoPhangan" if lang == "ru" else "🌴 Open GoPhangan",
                        "web_app": {"url": "https://phangan.fastpump.fun/"},
                    }
                ],
                [
                    {
                        "text": "📱 Добавить на домашний экран" if lang == "ru" else "📱 Add to Home Screen",
                        "url": "https://t.me/GoPhanganBot",
                    }
                ],
            ]
        }

        await _tg(
            "sendMessage",
            chat_id=chat_id,
            text=welcome,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    return Response(status_code=200)


# ── Webhook registration (called on app startup) ─────────────────────────

async def register_webhook(base_url: str) -> None:
    """Set Telegram webhook to point to our endpoint."""
    webhook_url = f"{base_url}/api/bot/webhook"
    result = await _tg("setWebhook", url=webhook_url)
    if result.get("ok"):
        logger.info("✅ Telegram webhook registered: %s", webhook_url)
    else:
        logger.error("❌ Failed to register webhook: %s", result)
