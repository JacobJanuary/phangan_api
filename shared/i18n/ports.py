"""Translation store port."""

from __future__ import annotations

from typing import Protocol


# Translations are returned as { screen: { key: value } } to match the
# frontend's i18n bundle shape.
Translations = dict[str, dict[str, str]]


class ITranslationStore(Protocol):
    """Hexagonal port for fetching translation bundles."""

    async def get_bundle(self, language: str) -> Translations:
        """Return all translations for `language`.

        Implementations SHOULD fall back to a default language (e.g. "en") when
        the requested one yields no rows so the UI is never blank.
        """
        ...
