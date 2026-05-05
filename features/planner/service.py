"""Vibe Pilot day-planner use case."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import asyncpg

from core.config import Constants, Settings
from core.exceptions import (
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from features.planner.prompt import SYSTEM_PROMPT
from features.planner.repository import PlannerRepository
from features.planner.schemas import PlannerRequest
from shared.ai.anthropic_adapter import AnthropicProvider
from shared.ai.cascade import CascadeOrchestrator, CascadeStep
from shared.ai.openai_adapter import OpenAICompatibleProvider
from shared.ai.ports import CompletionRequest
from shared.distance.haversine import road_km, travel_minutes

logger = logging.getLogger(__name__)

DEFAULT_DURATION: dict[str, int] = {
    "sport": 75,
    "chill": 60,
    "education": 90,
    "party": 180,
    "business": 60,
}


@dataclass(slots=True)
class PlannerService:
    pool: asyncpg.Pool
    settings: Settings
    constants: Constants

    # ── Public use case ──────────────────────────────────────────────

    async def generate_plan(
        self, *, user_id: int, body: PlannerRequest
    ) -> dict[str, Any]:
        try:
            target_date = date.fromisoformat(body.date)
        except ValueError as exc:
            raise ValidationError("Invalid date format. Use YYYY-MM-DD.") from exc

        # Snap GPS to ~1.1km grid for stable cache keys.
        body = body.model_copy(update={
            "lat": round(body.lat, 2),
            "lng": round(body.lng, 2),
        })

        repo = PlannerRepository(pool=self.pool)
        user_row = await repo.get_user_profile(user_id)
        if user_row is None:
            raise NotFoundError("User not found")

        events_rows = await repo.fetch_liked_events_for_date(
            user_id=user_id, target_date=target_date
        )
        if not events_rows:
            return self._empty_plan(body, saved=0, message="empty")

        pref_rows = await repo.fetch_preferences(user_id)
        liked: dict[str, int] = {}
        disliked: dict[str, int] = {}
        for row in pref_rows:
            cat = row["category"] or "Other"
            (liked if row["direction"] == "right" else disliked)[cat] = row["cnt"]

        events_data = self._build_events_data(events_rows, body)
        if not events_data:
            return self._empty_plan(body, saved=len(events_rows), message="all-past")

        distance_matrix = self._build_distance_matrix(events_data)

        ai_input = {
            "user": {
                "name": user_row["first_name"] or "Friend",
                "gender": user_row["gender"] or "unknown",
                "mood": user_row["mood"] or "explore",
                "location": {"lat": body.lat, "lng": body.lng},
                "preferences": {"liked": liked, "disliked": disliked},
            },
            "target_date": body.date,
            "language": body.lang,
            "events": events_data,
            "distance_matrix": distance_matrix,
        }

        input_hash = hashlib.sha256(
            json.dumps(ai_input, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        plan: dict | None = None
        if not body.force_refresh:
            plan = await repo.get_cached_plan(
                user_id=user_id, target_date=target_date
            )
            if plan:
                logger.info(
                    "Vibe Pilot cache HIT",
                    extra={"user_id": user_id, "date": body.date},
                )

        if plan is None:
            plan = await self._call_ai_cascade(ai_input, body)
            await repo.upsert_cached_plan(
                user_id=user_id,
                target_date=target_date,
                input_hash=input_hash,
                plan=plan,
            )

        return self._build_response(plan, events_data, body, saved=len(events_rows))

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_title(title_jsonb: Any, lang: str) -> str:
        if isinstance(title_jsonb, dict):
            return (
                title_jsonb.get(lang)
                or title_jsonb.get("en")
                or title_jsonb.get("ru")
                or str(title_jsonb)
            )
        if isinstance(title_jsonb, str):
            try:
                parsed = json.loads(title_jsonb)
                if isinstance(parsed, dict):
                    return (
                        parsed.get(lang)
                        or parsed.get("en")
                        or parsed.get("ru")
                        or title_jsonb
                    )
            except (json.JSONDecodeError, TypeError):
                pass
            return title_jsonb
        return str(title_jsonb)

    def _build_events_data(
        self, events_rows: list[asyncpg.Record], body: PlannerRequest
    ) -> list[dict]:
        current_minutes = 0
        if body.current_time:
            try:
                ch, cm = map(int, body.current_time[:5].split(":"))
                current_minutes = ch * 60 + cm
            except Exception:
                current_minutes = 0

        events_data: list[dict] = []
        for row in events_rows:
            vlat = row["venue_lat"]
            vlng = row["venue_lng"]
            cat = (row["category"] or "Other").lower()
            dist = (
                road_km(body.lat, body.lng, vlat, vlng,
                        factor=self.constants.HAVERSINE_ROAD_FACTOR)
                if vlat and vlng
                else None
            )
            time_str = (row["event_time"] or "")[:5] if row["event_time"] else "TBD"
            duration = DEFAULT_DURATION.get(cat, 60)

            if body.current_time and time_str != "TBD" and current_minutes > 0:
                try:
                    eh, em = map(int, time_str.split(":"))
                    if eh * 60 + em + duration <= current_minutes:
                        continue
                except Exception:
                    pass

            events_data.append({
                "id": str(row["id"]),
                "title": self._extract_title(row["title"], body.lang),
                "category": row["category"] or "Other",
                "time": time_str,
                "duration_min": duration,
                "location": row["location_name"] or "",
                "coords": ({"lat": vlat, "lng": vlng} if vlat and vlng else None),
                "distance_from_user_km": dist,
                "price_thb": row["price_thb"] or 0,
            })
        return events_data

    def _build_distance_matrix(self, events_data: list[dict]) -> dict[str, dict]:
        matrix: dict[str, dict] = {}
        coords_events = [e for e in events_data if e["coords"]]
        for i, ea in enumerate(coords_events):
            for j, eb in enumerate(coords_events):
                if i == j:
                    continue
                dist = road_km(
                    ea["coords"]["lat"], ea["coords"]["lng"],
                    eb["coords"]["lat"], eb["coords"]["lng"],
                    factor=self.constants.HAVERSINE_ROAD_FACTOR,
                )
                matrix[f"{ea['id']}→{eb['id']}"] = {
                    "km": dist,
                    "min": travel_minutes(dist, kmh=self.constants.SCOOTER_KMH),
                }
        return matrix

    def _build_cascade(self) -> CascadeOrchestrator:
        steps: list[CascadeStep] = []

        if self.settings.ANTHROPIC_API_KEY:
            steps.append(CascadeStep(
                provider=AnthropicProvider(
                    api_key=self.settings.ANTHROPIC_API_KEY,
                    model="claude-haiku-4-5-20251001",
                    name="anthropic_true",
                ),
                max_attempts=2,
            ))
        if self.settings.DEEPSEEK_API_KEY:
            steps.append(CascadeStep(
                provider=OpenAICompatibleProvider(
                    api_key=self.settings.DEEPSEEK_API_KEY,
                    model="deepseek-chat",
                    base_url="https://api.deepseek.com",
                    name="deepseek",
                ),
                max_attempts=1,
            ))
        if not steps:
            raise ExternalServiceError(
                "No AI provider configured for Vibe Pilot",
                details={"hint": "set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY"},
            )
        return CascadeOrchestrator(steps=steps)

    async def _call_ai_cascade(
        self, ai_input: dict, body: PlannerRequest
    ) -> dict:
        time_instruction = ""
        if body.current_time:
            time_instruction = (
                f"\nCRITICAL: The current time is {body.current_time}. "
                f"You MUST NOT schedule any events that have already started AND finished. "
                f"Begin the plan from the currently available (ongoing or upcoming) events.\n"
            )

        user_prompt = (
            f"Plan the optimal day for {body.date}. "
            f"Language: {'Russian' if body.lang == 'ru' else 'English'}.\n"
            f"{time_instruction}\n"
            f"Input data:\n{json.dumps(ai_input, ensure_ascii=False, indent=2)}"
        )

        cascade = self._build_cascade()
        raw_text = await cascade.complete(
            CompletionRequest(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
            )
        )
        return self._parse_plan_json(raw_text)

    @staticmethod
    def _parse_plan_json(raw_text: str) -> dict:
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExternalServiceError(
                "AI planner returned invalid JSON",
                details={"snippet": text[:200], "error": str(exc)},
            ) from exc

    @staticmethod
    def _empty_plan(
        body: PlannerRequest, *, saved: int, message: str
    ) -> dict[str, Any]:
        if message == "empty":
            note_ru = "У тебя нет сохранённых событий на этот день. Свайпни пару карточек!"
            note_en = "You have no saved events for this day. Swipe some cards!"
        else:
            note_ru = "Событий нет."
            note_en = "No events."
        return {
            "plan_name": "Нет событий" if body.lang == "ru" else "No events",
            "date": body.date,
            "total_events": 0,
            "saved_events_count": saved,
            "timeline": [],
            "skipped": [],
            "ai_note": note_ru if body.lang == "ru" else note_en,
        }

    @staticmethod
    def _build_response(
        plan: dict,
        events_data: list[dict],
        body: PlannerRequest,
        *,
        saved: int,
    ) -> dict[str, Any]:
        events_by_id = {str(e["id"]): e for e in events_data}

        for item in plan.get("timeline", []):
            ev = events_by_id.get(str(item.get("event_id", "")))
            if ev:
                item["title"] = ev["title"]
                item["location"] = ev["location"]
                item["lat"] = ev["coords"]["lat"] if ev["coords"] else None
                item["lng"] = ev["coords"]["lng"] if ev["coords"] else None
                item["category"] = ev["category"]
                item["price_thb"] = ev["price_thb"]

        for item in plan.get("skipped", []):
            ev = events_by_id.get(str(item.get("event_id", "")))
            if ev:
                item["title"] = ev["title"]
                item["time"] = ev["time"]
                item["location"] = ev.get("location", "")
                item["lat"] = ev["coords"]["lat"] if ev.get("coords") else None
                item["lng"] = ev["coords"]["lng"] if ev.get("coords") else None
                item["category"] = ev.get("category", "")
                item["price_thb"] = ev.get("price_thb", 0)

        timeline_ids = {
            str(item.get("event_id", "")) for item in plan.get("timeline", [])
        }
        all_candidates = [
            {
                "event_id": ev["id"],
                "title": ev["title"],
                "time": ev["time"],
                "location": ev["location"],
                "lat": ev["coords"]["lat"] if ev["coords"] else None,
                "lng": ev["coords"]["lng"] if ev["coords"] else None,
                "category": ev["category"],
                "price_thb": ev["price_thb"],
                "duration_min": ev["duration_min"],
            }
            for ev in events_data
            if ev["id"] not in timeline_ids
        ]

        total_travel = sum(
            item.get("travel_from_previous_km", 0)
            for item in plan.get("timeline", [])
        )

        return {
            "plan_name": plan.get("plan_name", "Your Day Plan"),
            "date": body.date,
            "total_events": len(plan.get("timeline", [])),
            "saved_events_count": saved,
            "total_travel_km": round(total_travel, 1),
            "timeline": plan.get("timeline", []),
            "skipped": plan.get("skipped", []),
            "all_candidates": all_candidates,
            "ai_note": plan.get("ai_note", ""),
        }
