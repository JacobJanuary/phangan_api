"""Facepile repository — DB queries for swipes + phantom pool."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from shared.facepile.selector import Phantom


@dataclass(frozen=True, slots=True)
class RealAttendee:
    """An aesthetic real-user avatar that swiped right on an event."""

    event_id: int
    avatar_path: str
    gender: str | None


@dataclass(slots=True)
class FacepileRepository:
    """Read-only access to swipes + users for facepile composition."""

    pool: asyncpg.Pool

    async def count_right_swipes_per_event(
        self, event_ids: list[int]
    ) -> dict[int, int]:
        if not event_ids:
            return {}
        rows = await self.pool.fetch(
            """
            SELECT event_id, COUNT(*) AS cnt
            FROM user_swipes
            WHERE event_id = ANY($1) AND direction = 'right'
            GROUP BY event_id
            """,
            event_ids,
        )
        return {row["event_id"]: row["cnt"] for row in rows}

    async def aesthetic_real_attendees(
        self, event_ids: list[int]
    ) -> list[RealAttendee]:
        if not event_ids:
            return []
        rows = await self.pool.fetch(
            """
            SELECT s.event_id, u.avatar_path, u.gender
            FROM user_swipes s
            JOIN users u ON u.id = s.user_id
            WHERE s.event_id = ANY($1)
              AND s.direction = 'right'
              AND u.is_phantom = false
              AND u.is_aesthetic = true
              AND u.avatar_path IS NOT NULL
            ORDER BY s.event_id, s.swiped_at DESC
            """,
            event_ids,
        )
        return [
            RealAttendee(
                event_id=row["event_id"],
                avatar_path=row["avatar_path"],
                gender=row["gender"],
            )
            for row in rows
        ]

    async def phantom_pool_by_mood(self) -> dict[str, list[Phantom]]:
        rows = await self.pool.fetch(
            """
            SELECT id, avatar_path, gender, mood
            FROM users
            WHERE is_phantom = true
              AND avatar_path IS NOT NULL
            ORDER BY RANDOM()
            """
        )
        pool: dict[str, list[Phantom]] = {}
        for row in rows:
            mood = row["mood"] or "party"
            pool.setdefault(mood, []).append(
                Phantom(
                    avatar_path=row["avatar_path"],
                    gender=row["gender"],
                    mood=mood,
                )
            )
        return pool
