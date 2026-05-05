"""Events use cases."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg

from core.config import Settings
from core.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from features.events.builders import build_event, parse_jsonb_dict
from features.events.repository import EventsRepository
from features.events.schemas import EventUpdate

logger = logging.getLogger(__name__)

_ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_TARGET_IMAGE_WIDTH = 600


@dataclass(slots=True)
class EventsService:
    pool: asyncpg.Pool
    settings: Settings
    facepile_service: object | None = None  # shared.facepile.service.FacepileService
    distance_service: object | None = None  # shared.distance.service.DistanceService

    @staticmethod
    def _now_today_tomorrow() -> tuple[datetime, date, date]:
        now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
        today = now_bkk.date()
        tomorrow = date.fromordinal(today.toordinal() + 1)
        return now_bkk, today, tomorrow

    async def list_events(
        self,
        *,
        user_id: int,
        lang: str,
        category: str,
        date_filter: str,
        limit: int,
        offset: int,
        user_lat: float | None,
        user_lng: float | None,
    ) -> dict:
        now_bkk, today, tomorrow = self._now_today_tomorrow()
        repo = EventsRepository(pool=self.pool)
        rows, total = await repo.list_upcoming(
            user_id=user_id,
            category=category,
            date_filter=date_filter,
            today=today,
            tomorrow=tomorrow,
            limit=limit,
            offset=offset,
        )

        events = [
            build_event(
                row,
                lang=lang,
                today=today,
                tomorrow=tomorrow,
                now_bkk=now_bkk,
                media_base_url=self.settings.PUBLIC_MEDIA_BASE_URL,
            )
            for row in rows
        ]

        if events:
            await self._enrich_facepile(events, user_id=user_id)
        if events and user_lat is not None and user_lng is not None:
            await self._enrich_distances(events, user_lat, user_lng)

        return {
            "events": events,
            "total": total,
            "filters": {
                "lang": lang,
                "date": date_filter or "all",
                "category": category or "all",
            },
        }

    async def get_event(self, event_id: int, *, user_id: int, lang: str) -> dict:
        now_bkk, today, tomorrow = self._now_today_tomorrow()
        repo = EventsRepository(pool=self.pool)
        row = await repo.get_one(event_id)
        if row is None:
            raise NotFoundError("Event not found")

        event = build_event(
            row,
            lang=lang,
            today=today,
            tomorrow=tomorrow,
            now_bkk=now_bkk,
            media_base_url=self.settings.PUBLIC_MEDIA_BASE_URL,
        )

        # Editor needs both languages — attach raw JSONB dicts.
        for field in ("title", "summary", "description"):
            event[f"{field}_raw"] = parse_jsonb_dict(row[field])

        await self._enrich_facepile([event], user_id=user_id)
        return event

    async def update_event(
        self, event_id: int, payload: EventUpdate, *, user_id: int
    ) -> dict:
        repo = EventsRepository(pool=self.pool)
        await self._verify_owner(repo, event_id=event_id, user_id=user_id)

        updated = await repo.update_owned(event_id, payload)
        if not updated:
            return {"status": "ok", "message": "No fields to update"}
        return {"status": "ok", "message": "Event updated successfully"}

    async def delete_event(self, event_id: int, *, user_id: int) -> dict:
        repo = EventsRepository(pool=self.pool)
        await self._verify_owner(repo, event_id=event_id, user_id=user_id)
        await repo.delete_with_dependencies(event_id)
        return {"status": "ok", "message": "Event deleted successfully"}

    async def upload_image(
        self,
        event_id: int,
        *,
        user_id: int,
        content: bytes,
        content_type: str | None,
    ) -> dict:
        if content_type not in _ALLOWED_IMAGE_MIMES:
            raise ValidationError(
                f"Unsupported format '{content_type}'. Allowed: JPEG, PNG, WebP."
            )
        if len(content) > _MAX_IMAGE_BYTES:
            raise ValidationError("File too large. Maximum size is 5 MB.")

        repo = EventsRepository(pool=self.pool)

        # Caller telegram_id (events.sender_id stores telegram_id).
        async with self.pool.acquire() as conn:
            caller_tg_id = await conn.fetchval(
                "SELECT telegram_id FROM users WHERE id = $1", user_id
            )

        meta = await repo.get_image_metadata(event_id)
        if meta is None:
            raise NotFoundError("Event not found")
        if meta["sender_id"] != caller_tg_id:
            raise AuthorizationError("Not authorized to edit this event")

        # Image processing — lazy import.
        from PIL import Image  # noqa: WPS433

        try:
            image = Image.open(BytesIO(content))
            if image.mode != "RGB":
                image = image.convert("RGB")
            if image.width > _TARGET_IMAGE_WIDTH:
                ratio = _TARGET_IMAGE_WIDTH / float(image.width)
                new_h = int(image.height * ratio)
                image = image.resize(
                    (_TARGET_IMAGE_WIDTH, new_h), Image.Resampling.LANCZOS
                )
        except Exception as exc:
            raise ValidationError(f"Cannot decode image: {exc}") from exc

        category = (meta["category"] or "other").lower()
        filename = f"event_{category}_{os.urandom(4).hex()}.webp"
        media_dir = Path(self.settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        save_path = media_dir / filename

        image.save(str(save_path), "WEBP", quality=85, method=6)
        logger.info(
            "Saved event image",
            extra={"event_id": event_id, "filename": filename},
        )

        old_path = meta["image_path"]
        if old_path:
            old_file = media_dir / old_path
            if old_file.is_file():
                try:
                    old_file.unlink()
                except OSError as exc:
                    logger.warning(
                        "Old image cleanup failed",
                        extra={"path": old_path, "error": str(exc)},
                    )

        await repo.set_image_path(event_id, filename)
        return {
            "status": "ok",
            "message": "Image uploaded successfully",
            "imageUrl": f"{self.settings.PUBLIC_MEDIA_BASE_URL}/{filename}",
        }

    # ── Internal helpers ─────────────────────────────────────────────

    async def _verify_owner(
        self, repo: EventsRepository, *, event_id: int, user_id: int
    ) -> None:
        async with self.pool.acquire() as conn:
            caller_tg_id = await conn.fetchval(
                "SELECT telegram_id FROM users WHERE id = $1", user_id
            )
        owner_tg_id = await repo.get_owner_telegram_id(event_id)
        if owner_tg_id is None:
            raise NotFoundError("Event not found")
        if owner_tg_id != caller_tg_id:
            raise AuthorizationError("Not authorized to edit this event")

    async def _enrich_facepile(self, events: list[dict], *, user_id: int) -> None:
        if self.facepile_service is None:
            logger.debug("FacepileService not wired — skipping enrichment")
            return

        try:
            viewer_gender = await EventsRepository(
                pool=self.pool
            ).get_viewer_gender(user_id)
        except Exception:
            viewer_gender = None

        event_ids = [int(ev["id"]) for ev in events]
        event_categories = {int(ev["id"]): ev.get("category", "") for ev in events}
        try:
            facepile_data = await self.facepile_service.get_batch(  # type: ignore[attr-defined]
                event_ids=event_ids,
                event_categories=event_categories,
                viewer_gender=viewer_gender,
            )
        except Exception as exc:
            logger.warning("Facepile enrichment failed: %s", exc)
            return

        for ev in events:
            fp = facepile_data.get(int(ev["id"]))
            if fp:
                ev["attendeeCount"] = fp["count"]
                ev["facepileUrls"] = fp["avatarUrls"]

    async def _enrich_distances(
        self, events: list[dict], user_lat: float, user_lng: float
    ) -> None:
        if self.distance_service is None:
            logger.debug("DistanceService not wired — skipping enrichment")
            return
        try:
            await self.distance_service.enrich_events(  # type: ignore[attr-defined]
                events, user_lat=user_lat, user_lng=user_lng
            )
        except Exception as exc:
            logger.warning("Distance enrichment failed: %s", exc)
