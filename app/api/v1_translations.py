"""
Lightweight i18n endpoint – allows fetching translations without re-authenticating.

GET /api/v1/translations?lang=ru  →  { "welcome": { ... }, "swipe_feed": { ... }, ... }
"""

from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db.database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["i18n"])


@router.get("/translations", summary="Get all UI translations for a language")
async def get_translations(
    lang: str = Query("ru", description="Language code: ru | en"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """
    Returns all UI translations grouped by section.

    Response shape:
    ```json
    {
      "welcome": { "tag_label": "Your guide", ... },
      "swipe_feed": { "filter_all": "All", ... },
      ...
    }
    ```
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT screen, key, value
            FROM app_i18n
            WHERE lang = $1
            ORDER BY screen, key
            """,
            lang,
        )
        # Fallback to 'en' if nothing found for requested lang
        if not rows:
            rows = await conn.fetch(
                "SELECT screen, key, value FROM app_i18n WHERE lang = 'en' ORDER BY screen, key"
            )

    result: dict = {}
    for r in rows:
        result.setdefault(r["screen"], {})[r["key"]] = r["value"]

    return result
