"""Auth-specific repository (i18n + onboarding fetches)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import asyncpg


@dataclass(slots=True)
class AuthRepository:
    pool: asyncpg.Pool

    async def get_onboarding(self, language: str) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT onboarding FROM ui_translations WHERE lang_code = $1",
                language,
            )
            if not row:
                row = await conn.fetchrow(
                    "SELECT onboarding FROM ui_translations WHERE lang_code = 'en'"
                )
        if not row or not row["onboarding"]:
            return {}
        raw = row["onboarding"]
        return raw if isinstance(raw, dict) else json.loads(raw)

    async def get_ui_translations(self, language: str) -> dict[str, dict[str, str]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT screen, key, value FROM app_i18n
                WHERE lang = $1
                ORDER BY screen, key
                """,
                language,
            )
            if not rows:
                rows = await conn.fetch(
                    """
                    SELECT screen, key, value FROM app_i18n
                    WHERE lang = 'en'
                    ORDER BY screen, key
                    """
                )

        out: dict[str, dict[str, str]] = {}
        for r in rows:
            out.setdefault(r["screen"], {})[r["key"]] = r["value"]
        return out
