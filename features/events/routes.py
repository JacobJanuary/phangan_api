"""HTTP routes for events feature."""

from __future__ import annotations

from typing import Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from core.config import Settings
from core.dependencies import get_current_user_id, get_pool_dep, get_settings_dep
from features.events.schemas import EventUpdate
from features.events.service import EventsService

router = APIRouter(prefix="/api/v1", tags=["events-v1"])


def _service(pool: asyncpg.Pool, settings: Settings) -> EventsService:
    return EventsService(pool=pool, settings=settings)


@router.get(
    "/events",
    summary="List upcoming events (JWT-protected, frontend contract)",
)
async def list_events(
    lang: Literal["en", "ru"] = Query(default="ru"),
    category: Optional[Literal["party", "chill", "all"]] = Query(default="all"),
    date_filter: Optional[Literal["today", "tomorrow", "all"]] = Query(
        default="all", alias="date"
    ),
    limit: int = Query(default=30, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_lat: Optional[float] = Query(default=None, alias="lat"),
    user_lng: Optional[float] = Query(default=None, alias="lng"),
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    return await _service(pool, settings).list_events(
        user_id=user_id,
        lang=lang,
        category=category or "all",
        date_filter=date_filter or "all",
        limit=limit,
        offset=offset,
        user_lat=user_lat,
        user_lng=user_lng,
    )


@router.get("/events/{event_id}", summary="Get a single event by ID")
async def get_event(
    event_id: int,
    lang: Literal["en", "ru"] = Query(default="ru"),
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    return await _service(pool, settings).get_event(
        event_id, user_id=user_id, lang=lang
    )


@router.put("/events/{event_id}", summary="Update an event (Only Author)")
async def update_event(
    event_id: int,
    payload: EventUpdate,
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    return await _service(pool, settings).update_event(
        event_id, payload, user_id=user_id
    )


@router.delete("/events/{event_id}", summary="Delete an event (Only Author)")
async def delete_event(
    event_id: int,
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    return await _service(pool, settings).delete_event(event_id, user_id=user_id)


@router.post(
    "/events/{event_id}/image",
    summary="Upload / replace event cover image (Only Author)",
    status_code=status.HTTP_200_OK,
)
async def upload_event_image(
    event_id: int,
    file: UploadFile = File(...),
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    content = await file.read()
    return await _service(pool, settings).upload_image(
        event_id,
        user_id=user_id,
        content=content,
        content_type=file.content_type,
    )
