"""Thin Telegram Bot API client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


@dataclass(slots=True)
class TelegramBotClient:
    """Minimal HTTP client for Telegram Bot API methods we use."""

    bot_token: str
    timeout_s: float = 10.0

    async def call(self, method: str, **payload: Any) -> dict:
        if not self.bot_token:
            raise ValueError("TelegramBotClient.bot_token is empty")
        url = _TELEGRAM_API.format(token=self.bot_token, method=method)
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
        if not data.get("ok"):
            logger.warning(
                "Telegram API non-ok response",
                extra={"method": method, "response": data},
            )
        return data
