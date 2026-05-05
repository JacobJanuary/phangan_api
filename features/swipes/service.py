"""Swipes use cases."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from core.config import Settings
from core.exceptions import NotFoundError
from features.events.builders import build_event
from features.events.service import EventsService
from features.swipes.repository import SwipesRepository
from features.swipes.schemas import SwipeCreate

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SwipesService:
    pool: asyncpg.Pool
    settings: Settings

    async def save_swipe(self, *, user_id: int, payload: SwipeCreate) -> None:
        try:
            await SwipesRepository(pool=self.pool).upsert_swipe(
                user_id=user_id,
                event_id=payload.event_id,
                direction=payload.direction,
            )
        except asyncpg.ForeignKeyViolationError as exc:
            raise NotFoundError("Event not found") from exc

    async def reset_swipes(self, *, user_id: int) -> None:
        await SwipesRepository(pool=self.pool).reset_for_user(user_id)

    async def my_vibe(
        self,
        *,
        user_id: int,
        lang: str,
        include_past: bool,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
        today = now_bkk.date()
        tomorrow = date.fromordinal(today.toordinal() + 1)

        repo = SwipesRepository(pool=self.pool)
        upcoming_rows = await repo.fetch_upcoming(user_id)
        past_total = await repo.count_past(user_id)

        media_base = self.settings.PUBLIC_MEDIA_BASE_URL

        def _to_event(row: asyncpg.Record) -> dict:
            ev = build_event(
                row,
                lang=lang,
                today=today,
                tomorrow=tomorrow,
                now_bkk=now_bkk,
                media_base_url=media_base,
            )
            ev["swiped_at"] = (
                row["swiped_at"].isoformat() if row["swiped_at"] else None
            )
            return ev

        upcoming = [_to_event(r) for r in upcoming_rows]

        result: dict[str, Any] = {"upcoming": upcoming, "past_total": past_total}

        if include_past:
            past_rows = await repo.fetch_past(user_id, limit=limit, offset=offset)
            result["past"] = [_to_event(r) for r in past_rows]

        # Reuse the same facepile enrichment as the events feature.
        all_events = upcoming + result.get("past", [])
        if all_events:
            events_service = EventsService(pool=self.pool, settings=self.settings)
            await events_service._enrich_facepile(all_events, user_id=user_id)  # noqa: SLF001

        return result
