"""Auth use cases — Telegram initData → user + JWT + i18n bundle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import asyncpg
from fastapi import BackgroundTasks

from core.config import Settings
from core.exceptions import AuthenticationError, ValidationError
from core.jwt import create_access_token
from features.auth.repository import AuthRepository
from features.auth.schemas import InitDataPayload
from features.users.language_detection import detect_language_sync
from features.users.repository import UsersRepository
from features.users.workers import (
    process_avatar_background,
    process_gender_background,
    process_language_background,
)
from shared.ai.cascade import CascadeOrchestrator
from shared.telegram.auth import validate_init_data

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuthService:
    pool: asyncpg.Pool
    settings: Settings
    cascade: CascadeOrchestrator | None = None

    async def init_session(
        self,
        payload: InitDataPayload,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        try:
            user_data = validate_init_data(payload.initData, self.settings.BOT_TOKEN)
        except Exception as exc:
            raise AuthenticationError("Invalid Telegram signature") from exc

        telegram_id = user_data.get("id")
        if not telegram_id:
            raise ValidationError("Missing user ID in initData")

        first_name = user_data.get("first_name", "Unknown")
        photo_url = user_data.get("photo_url", "")
        t_lang = str(user_data.get("language_code", "")).lower()

        # Layers 1–3: synchronous language detection.
        language = detect_language_sync(first_name, t_lang)

        users_repo = UsersRepository(pool=self.pool)
        auth_repo = AuthRepository(pool=self.pool)

        row = await users_repo.upsert_on_login(
            telegram_id=telegram_id,
            first_name=first_name,
            language=language,
        )
        internal_id = row["id"]
        db_gender = row["gender"] or "unknown"
        current_mood = row["mood"]
        avatar_path = row["avatar_path"]
        db_language = row["language"] or language
        updated_at = row["updated_at"]
        is_new = row["is_new"]

        # Effective UI language: returning users keep what they had in DB
        # (otherwise switching Telegram client language would silently swap
        # their interface to a different locale on every login). New users
        # take whatever was just detected.
        effective_language = language if is_new else db_language

        # Mood TTL — wipe stale moods.
        if current_mood is not None and UsersRepository.is_mood_stale(
            updated_at, hours_ttl=6
        ):
            await users_repo.expire_stale_mood(internal_id)
            current_mood = None

        onboarding = await auth_repo.get_onboarding(effective_language)
        ui_translations = await auth_repo.get_ui_translations(effective_language)

        # Background enrichment workers.
        if is_new or db_gender == "unknown":
            background_tasks.add_task(
                process_gender_background,
                pool=self.pool,
                telegram_id=telegram_id,
                first_name=first_name,
                language=language,
                cascade=self.cascade,
            )
        if is_new:
            background_tasks.add_task(
                process_language_background,
                pool=self.pool,
                telegram_id=telegram_id,
                first_name=first_name,
                telegram_language_code=t_lang,
                bot_token=self.settings.BOT_TOKEN,
            )
        if is_new or not avatar_path:
            background_tasks.add_task(
                process_avatar_background,
                pool=self.pool,
                settings=self.settings,
                telegram_id=telegram_id,
                photo_url=photo_url,
            )

        token = create_access_token(
            payload={"sub": str(internal_id), "telegram_id": telegram_id},
            secret=self.settings.JWT_SECRET,
            algorithm=self.settings.JWT_ALGORITHM,
            expires_minutes=self.settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        )

        return {
            "token": token,
            "user": {
                "id": str(internal_id),
                "telegram_id": str(telegram_id),
                "first_name": first_name,
                "gender": db_gender,
                "current_mood": current_mood,
                "lang_code": effective_language,
            },
            "i18n": {
                "onboarding": onboarding,
                "ui": ui_translations,
            },
        }
