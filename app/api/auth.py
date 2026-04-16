"""
Auth API endpoints for Zero-Click Registration.
"""

from __future__ import annotations

import json
import logging

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.telegram_auth import validate_telegram_data
from app.db.database import get_pool
from app.core.jwt import create_access_token
from app.services.user_worker import (
    process_gender_background,
    process_avatar_background,
    process_language_background,
    detect_language,
    _has_cyrillic,
    _name_in_ru_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class InitDataPayload(BaseModel):
    initData: str

@router.post(
    "/init",
    summary="Zero-Click Registration via Telegram Mini App",
    description="Validates Telegram initData, registers or updates user, and returns JWT with localized UI texts.",
)
async def init_auth(
    payload: InitDataPayload,
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    
    # 1. Validate Telegram Signature
    user_data = validate_telegram_data(payload.initData)

    telegram_id = user_data.get("id")
    first_name = user_data.get("first_name", "Unknown")
    photo_url = user_data.get("photo_url", "")
    t_lang = str(user_data.get("language_code", "")).lower()
    
    # Quick synchronous language detection (layers 1-3, no API call)
    # Layer 1: Cyrillic in name → ru
    # Layer 2: Telegram language_code → ru
    # Layer 3: Name in Russian dictionary → ru
    if _has_cyrillic(first_name):
        language = "ru"
    elif "ru" in t_lang:
        language = "ru"
    else:
        clean_name = first_name.strip().split()[0] if first_name.strip() else first_name
        language = "ru" if _name_in_ru_dict(clean_name) else "en"

    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing user ID in initData",
        )

    # 2. Check if user exists & Fast Insert
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO users (telegram_id, first_name, is_phantom, mood, language)
                VALUES ($1, $2, False, NULL, $3)
                ON CONFLICT (telegram_id) DO UPDATE 
                SET first_name = EXCLUDED.first_name
                RETURNING id, gender, mood, avatar_path, language, updated_at, (xmax = 0) AS is_new
                """,
                telegram_id,
                first_name,
                language,
            )
            
            internal_id = row["id"]
            db_gender = row["gender"] or "unknown"
            current_mood = row["mood"]
            avatar_path = row["avatar_path"]
            db_language = row["language"] or language
            updated_at = row["updated_at"]
            is_new = row["is_new"]

            # --- Context TTL Logic ---
            if current_mood is not None and updated_at is not None:
                from datetime import datetime, timezone
                
                now_utc = datetime.now(timezone.utc)
                # Parse if needed, but asyncpg returns timezone-aware datetime for TIMESTAMPTZ
                hours_since = (now_utc - updated_at).total_seconds() / 3600.0
                
                if hours_since > 6:
                    await conn.execute(
                        "UPDATE users SET mood = NULL, updated_at = NOW() WHERE id = $1",
                        internal_id
                    )
                    current_mood = None
            # -------------------------

            # 3. Fetch localized onboarding translations
            translation_row = await conn.fetchrow(
                "SELECT onboarding FROM ui_translations WHERE lang_code = $1", 
                language
            )
            if not translation_row:
                translation_row = await conn.fetchrow(
                    "SELECT onboarding FROM ui_translations WHERE lang_code = 'en'"
                )
            onboarding_data = json.loads(translation_row["onboarding"]) if translation_row else {}

            # 4. Fetch all UI screen translations from app_i18n (single query, group in Python)
            # Fallback chain: requested lang -> 'en' -> 'ru'
            i18n_rows = await conn.fetch(
                """
                SELECT screen, key, value FROM app_i18n
                WHERE lang = $1
                ORDER BY screen, key
                """,
                language
            )
            if not i18n_rows:
                i18n_rows = await conn.fetch(
                    "SELECT screen, key, value FROM app_i18n WHERE lang = 'en' ORDER BY screen, key"
                )

            # Group by screen into dict-of-dicts
            ui_translations: dict = {}
            for r in i18n_rows:
                ui_translations.setdefault(r["screen"], {})[r["key"]] = r["value"]

        except asyncpg.UndefinedTableError:
            logger.error("Table 'users' or 'ui_translations' does not exist in the database.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database schema not ready",
            )
        except Exception as e:
            logger.error("DB error during login: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal database error",
            )

    # 4. Queue Background Processing for New Users (or if data missing)
    if is_new or db_gender == "unknown":
        # We keep ML fast by delegating to the background
        # Gender detecting LLM takes 1-2 seconds, so doing it concurrently here yields sub-second API responses
        background_tasks.add_task(
            process_gender_background,
            pool=pool,
            telegram_id=telegram_id,
            first_name=first_name,
            language=language,
        )

    # Language refinement via getChat API (background, layer 4)
    if is_new:
        background_tasks.add_task(
            process_language_background,
            pool=pool,
            telegram_id=telegram_id,
            first_name=first_name,
            telegram_language_code=t_lang,
        )

    if is_new or not avatar_path:
        background_tasks.add_task(
            process_avatar_background,
            pool=pool,
            telegram_id=telegram_id,
            photo_url=photo_url,
        )

    # 5. Generate JWT Token
    jwt_token = create_access_token({"sub": str(internal_id), "telegram_id": telegram_id})

    return {
        "token": jwt_token,
        "user": {
            "id": str(internal_id),
            "telegram_id": str(telegram_id),
            "first_name": first_name,
            "gender": db_gender,
            "current_mood": current_mood,
            "lang_code": db_language if not is_new else language,
        },
        "i18n": {
            "onboarding": onboarding_data,
            "ui": ui_translations,
        }
    }
