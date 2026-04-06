"""
Users API endpoints for reading and modifying profile data.
"""

from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user_id
from app.db.database import get_pool
from app.schemas.user import UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.patch(
    "/me",
    summary="Update User Profile",
    description="Updates the current mood or gender for the authenticated user context extracted from JWT.",
)
async def update_me(
    user_update: UserUpdate,
    user_id: int = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    
    # Exclude unset fields from the payload
    update_data = user_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided for update",
        )
    
    # Map Pydantic field names → actual DB column names
    FIELD_TO_COLUMN = {
        "current_mood": "mood",
    }
    
    set_clauses = []
    args = []
    for idx, (key, val) in enumerate(update_data.items(), start=1):
        col = FIELD_TO_COLUMN.get(key, key)
        set_clauses.append(f"{col} = ${idx}")
        args.append(val)
        
    args.append(user_id)
    where_param_idx = len(args)
    
    set_query_fragment = ", ".join(set_clauses)
    
    query = f"""
        UPDATE users
        SET {set_query_fragment}, updated_at = NOW()
        WHERE id = ${where_param_idx}
        RETURNING id, telegram_id, first_name, gender, mood, avatar_path
    """
    
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(query, *args)
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User record not found",
                )
            
            return {
                "user": {
                    "id": str(row["id"]),
                    "telegram_id": str(row["telegram_id"]),
                    "first_name": row["first_name"],
                    "gender": row["gender"],
                    "current_mood": row["mood"],
                    "avatar": row["avatar_path"],
                }
            }
        except asyncpg.UndefinedTableError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database schema not ready",
            )
        except Exception as e:
            logger.error("Error updating user %d: %s", user_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal database error",
            )
