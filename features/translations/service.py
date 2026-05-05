"""Translations use cases — thin wrapper around the shared i18n store."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from shared.i18n.postgres_adapter import PostgresTranslationStore
from shared.i18n.ports import Translations


@dataclass(slots=True)
class TranslationsService:
    """Use cases for the translations slice."""

    pool: asyncpg.Pool

    async def get_bundle(self, language: str) -> Translations:
        store = PostgresTranslationStore(pool=self.pool)
        return await store.get_bundle(language)
