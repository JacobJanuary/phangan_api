"""SQL-only repository for the users slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

# Mapping from user-facing field names → underlying DB column names.
_PYDANTIC_TO_COLUMN: dict[str, str] = {
    "current_mood": "mood",
}


@dataclass(slots=True)
class UsersRepository:
    """All SQL touching the `users` table for the users feature."""

    pool: asyncpg.Pool

    async def upsert_on_login(
        self,
        *,
        telegram_id: int,
        first_name: str,
        language: str,
    ) -> dict[str, Any]:
        """INSERT or UPDATE the user, returning the row + `is_new` flag."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (telegram_id, first_name, is_phantom, mood, language)
                VALUES ($1, $2, False, NULL, $3)
                ON CONFLICT (telegram_id) DO UPDATE
                SET first_name = EXCLUDED.first_name
                RETURNING id, gender, mood, avatar_path, language, updated_at,
                         (xmax = 0) AS is_new
                """,
                telegram_id,
                first_name,
                language,
            )
        return dict(row)

    async def expire_stale_mood(self, user_id: int) -> None:
        """Reset `mood` to NULL when the context window has expired."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET mood = NULL, updated_at = NOW() WHERE id = $1",
                user_id,
            )

    async def get_onboarding_translations(self, language: str) -> str | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT onboarding FROM ui_translations WHERE lang_code = $1",
                language,
            )
            if not row:
                row = await conn.fetchrow(
                    "SELECT onboarding FROM ui_translations WHERE lang_code = 'en'"
                )
        return row["onboarding"] if row else None

    async def update_profile(
        self, user_id: int, fields: dict[str, Any]
    ) -> asyncpg.Record | None:
        """Dynamic UPDATE on the user row. Returns the refreshed row or None."""
        if not fields:
            return None

        set_clauses: list[str] = []
        args: list[Any] = []
        for idx, (key, val) in enumerate(fields.items(), start=1):
            col = _PYDANTIC_TO_COLUMN.get(key, key)
            set_clauses.append(f"{col} = ${idx}")
            args.append(val)

        args.append(user_id)
        where_idx = len(args)
        query = f"""
            UPDATE users
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = ${where_idx}
            RETURNING id, telegram_id, first_name, gender, mood, avatar_path
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def update_gender(self, telegram_id: int, gender: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET gender = $1 WHERE telegram_id = $2",
                gender,
                telegram_id,
            )

    async def update_language(self, telegram_id: int, language: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET language = $1 WHERE telegram_id = $2",
                language,
                telegram_id,
            )

    async def update_avatar(
        self, telegram_id: int, *, avatar_path: str, is_aesthetic: bool
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET is_aesthetic = $1, avatar_path = $2
                WHERE telegram_id = $3
                """,
                is_aesthetic,
                avatar_path,
                telegram_id,
            )

    async def get_telegram_id(self, user_id: int) -> int | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT telegram_id FROM users WHERE id = $1",
                user_id,
            )

    async def get_gender(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT gender FROM users WHERE id = $1",
                user_id,
            )

    @staticmethod
    def is_mood_stale(updated_at: datetime | None, hours_ttl: int) -> bool:
        if updated_at is None:
            return False
        from datetime import datetime as _dt
        from datetime import timezone as _tz

        elapsed = (_dt.now(_tz.utc) - updated_at).total_seconds() / 3600.0
        return elapsed > hours_ttl
