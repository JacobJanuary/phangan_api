"""HTTP routes for the Vibe Pilot planner."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from core.config import Constants, Settings, get_constants
from core.dependencies import get_current_user_id, get_pool_dep, get_settings_dep
from features.planner.schemas import PlannerRequest
from features.planner.service import PlannerService

router = APIRouter(prefix="/api/v1/planner", tags=["planner"])


def _constants() -> Constants:
    return get_constants()


@router.post("/generate")
async def generate_plan(
    body: PlannerRequest,
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    constants: Constants = Depends(_constants),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = PlannerService(pool=pool, settings=settings, constants=constants)
    return await service.generate_plan(user_id=user_id, body=body)
