"""Translations HTTP layer."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query

from core.dependencies import get_pool_dep
from features.translations.service import TranslationsService

router = APIRouter(prefix="/api/v1", tags=["i18n"])


@router.get("/translations", summary="Get all UI translations for a language")
async def get_translations(
    lang: str = Query("ru", description="Language code: ru | en"),
    pool: asyncpg.Pool = Depends(get_pool_dep),
) -> dict:
    """Return the full UI bundle grouped by screen, with `en` fallback."""
    service = TranslationsService(pool=pool)
    return await service.get_bundle(lang)
