"""Bot webhook HTTP endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response

from core.config import Settings
from core.dependencies import get_settings_dep
from features.bot.service import BotService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bot"])


@router.post("/api/bot/webhook", include_in_schema=False)
async def bot_webhook(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """Receive Telegram update; ALWAYS reply 200 so Telegram doesn't retry."""
    try:
        update = await request.json()
    except Exception:
        return Response(status_code=200)

    try:
        await BotService(settings=settings).handle_update(update)
    except Exception as exc:
        logger.exception("Bot webhook handler raised", extra={"error": str(exc)})

    return Response(status_code=200)
