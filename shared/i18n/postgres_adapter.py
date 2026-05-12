"""Postgres-backed translation store with optional cache layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

from shared.cache.ports import ICache
from shared.i18n.ports import ITranslationStore, Translations

logger = logging.getLogger(__name__)


def _bundle_cache_key(language: str) -> str:
    return f"i18n:bundle:{language}"


@dataclass(slots=True)
class PostgresTranslationStore(ITranslationStore):
    """Reads from `app_i18n`. Falls back to `fallback_language` when empty."""

    pool: asyncpg.Pool
    cache: ICache | None = None
    fallback_language: str = "en"
    cache_ttl_seconds: int = 300  # 5 minutes — translations change rarely

    async def get_bundle(self, language: str) -> Translations:
        if not language:
            raise ValueError("language must be non-empty")

        if self.cache is not None:
            cached = await self.cache.get(_bundle_cache_key(language))
            if cached is not None:
                return cached  # type: ignore[return-value]

        bundle = await self._load(language)
        if not bundle and language != self.fallback_language:
            logger.info(
                "i18n bundle empty — falling back",
                extra={"language": language, "fallback": self.fallback_language},
            )
            bundle = await self._load(self.fallback_language)

        if self.cache is not None:
            await self.cache.set(
                _bundle_cache_key(language), bundle, ttl_seconds=self.cache_ttl_seconds
            )
        return bundle

    async def _load(self, language: str) -> Translations:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT screen, key, value
                FROM app_i18n
                WHERE lang = $1
                ORDER BY screen, key
                """,
                language,
            )
        bundle: Translations = {}
        for row in rows:
            bundle.setdefault(row["screen"], {})[row["key"]] = row["value"]
        return bundle
