"""Background workers for asynchronous user enrichment."""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

from core.config import Settings
from features.users.avatar import fetch_and_process_avatar
from features.users.gender_detection import detect_gender
from features.users.language_detection import detect_language
from features.users.repository import UsersRepository
from shared.ai.cascade import CascadeOrchestrator

logger = logging.getLogger(__name__)


async def process_gender_background(
    *,
    pool: asyncpg.Pool,
    telegram_id: int,
    first_name: str,
    language: str,
    cascade: CascadeOrchestrator | None,
) -> None:
    logger.info("Gender worker started", extra={"telegram_id": telegram_id})
    gender = await detect_gender(first_name, language=language, cascade=cascade)
    try:
        await UsersRepository(pool=pool).update_gender(telegram_id, gender)
    except Exception as exc:
        logger.error(
            "Gender worker DB update failed",
            extra={"telegram_id": telegram_id, "error": str(exc)},
        )
        return
    logger.info(
        "Gender worker done",
        extra={"telegram_id": telegram_id, "gender": gender},
    )


async def process_language_background(
    *,
    pool: asyncpg.Pool,
    telegram_id: int,
    first_name: str,
    telegram_language_code: str,
    bot_token: str,
) -> None:
    logger.info("Language worker started", extra={"telegram_id": telegram_id})
    language = await detect_language(
        first_name,
        telegram_language_code=telegram_language_code,
        telegram_id=telegram_id,
        bot_token=bot_token,
    )
    try:
        await UsersRepository(pool=pool).update_language(telegram_id, language)
    except Exception as exc:
        logger.error(
            "Language worker DB update failed",
            extra={"telegram_id": telegram_id, "error": str(exc)},
        )
        return
    logger.info(
        "Language worker done",
        extra={"telegram_id": telegram_id, "language": language},
    )


async def process_avatar_background(
    *,
    pool: asyncpg.Pool,
    settings: Settings,
    telegram_id: int,
    photo_url: str,
) -> None:
    logger.info("Avatar worker started", extra={"telegram_id": telegram_id})
    result = await fetch_and_process_avatar(
        telegram_id=telegram_id,
        photo_url=photo_url,
        media_dir=Path(settings.MEDIA_DIR),
        avatars_subdir=settings.AVATARS_DIR,
    )
    if not result.avatar_path:
        return
    try:
        await UsersRepository(pool=pool).update_avatar(
            telegram_id,
            avatar_path=result.avatar_path,
            is_aesthetic=result.is_aesthetic,
        )
    except Exception as exc:
        logger.error(
            "Avatar worker DB update failed",
            extra={"telegram_id": telegram_id, "error": str(exc)},
        )
        return
    logger.info("Avatar worker done", extra={"telegram_id": telegram_id})
