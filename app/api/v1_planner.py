"""
Vibe Pilot 🧭 — AI Day Planner.

POST /api/v1/planner/generate
  Takes user's right-swiped events for a date, resolves time
  conflicts, optimizes the route, and returns a structured day plan
  via Gemini 2.5 Flash.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.db.database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/planner", tags=["planner"])

BKK = ZoneInfo("Asia/Bangkok")

# ── Constants ────────────────────────────────────────────────────────────────
# Model cascade: (model_name, max_attempts)
GEMINI_CASCADE = [
    ("gemini-3-flash-preview", 2),
    ("gemini-2.5-flash", 1),
    ("gemini-3.1-flash-lite-preview", 1),
]
ROAD_FACTOR = 1.4       # Haversine → approximate road distance
SCOOTER_KMH = 25        # Average scooter speed on Koh Phangan

# Default event durations by category (minutes)
DEFAULT_DURATION: dict[str, int] = {
    "sport":     75,
    "chill":     60,
    "education": 90,
    "party":     180,
    "business":  60,
}


# ── Request / Response schemas ───────────────────────────────────────────────

class PlannerRequest(BaseModel):
    date: str = Field(..., description="Target date YYYY-MM-DD")
    lat: float = Field(..., description="User latitude")
    lng: float = Field(..., description="User longitude")
    lang: Literal["en", "ru"] = Field(default="ru")


# ── Haversine ────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _road_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return round(_haversine_km(lat1, lng1, lat2, lng2) * ROAD_FACTOR, 1)


def _travel_min(dist_km: float) -> int:
    return max(1, math.ceil(dist_km / SCOOTER_KMH * 60))


# ── Gemini System Prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Vibe Pilot 🧭 — an AI day planner for travelers on Koh Phangan island, Thailand.

TASK: Build an optimized day plan from the user's liked events.

RULES:
1. RESOLVE TIME CONFLICTS: When events overlap (start times within duration of another), pick the best one based on:
   - User's proximity (closer = better, less wasted travel time)
   - User's preference profile (higher liked ratio in that category = preferred)
   - Gender relevance (skip "Women only" / "для женщин" events for male users, vice versa)
   - Price (if similar events, prefer cheaper or free)
   - Route optimization (minimize total zig-zag travel across the island)

2. ROUTE OPTIMIZATION: Consider sequential travel:
   - First event: travel from USER's current location
   - Subsequent events: travel from PREVIOUS event's venue (not from home)
   - Use the provided distance_matrix for venue-to-venue distances

3. TIME GAPS: Ensure at least (travel_time + 15 min buffer) between end of one event and start of next.
   If there's not enough time, skip the later event.

4. DURATION: Use the provided duration_min for each event. Never overlap events temporally.

5. PRIORITY ORDER: If forced to choose between competing events, prefer the user's top categories (highest liked count).

6. Be encouraging, friendly, and emoji-light in your reasons. Keep them concise — 1-2 sentences max.

7. Respond in the specified language.

OUTPUT: Return ONLY valid JSON (no markdown, no ```), strictly in this format:
{
  "plan_name": "Creative short name for this day plan (in user's language)",
  "timeline": [
    {
      "order": 1,
      "event_id": "123",
      "start_time": "08:00",
      "end_time": "09:15",
      "duration_min": 75,
      "travel_from_previous_km": 2.1,
      "travel_from_previous_min": 5,
      "reason": "Short explanation why chosen"
    }
  ],
  "skipped": [
    {
      "event_id": "456",
      "skip_reason": "Short explanation why skipped"
    }
  ],
  "ai_note": "Friendly summary of the whole day plan, 2-3 sentences"
}"""


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_plan(
    body: PlannerRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Generate an AI-optimized day plan from right-swiped events."""
    try:
        target_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    async with pool.acquire() as conn:
        # ── 1. Fetch user profile ────────────────────────────────────────
        user_row = await conn.fetchrow(
            "SELECT first_name, gender, mood FROM users WHERE id = $1",
            user_id,
        )
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        # ── 2. Fetch upcoming right-swiped events for target date ────────
        events_rows = await conn.fetch("""
            SELECT e.id, e.title, e.summary, e.category,
                   e.event_date, e.event_time, e.location_name, e.price_thb,
                   v.lat AS venue_lat, v.lng AS venue_lng
            FROM user_swipes s
            JOIN events e ON e.id = s.event_id
            LEFT JOIN venues v ON e.venue_id = v.id
            WHERE s.user_id = $1
              AND s.direction = 'right'
              AND e.event_date = $2
            ORDER BY e.event_time ASC NULLS LAST
        """, user_id, target_date)

        if not events_rows:
            return {
                "plan_name": "Нет событий" if body.lang == "ru" else "No events",
                "date": body.date,
                "total_events": 0,
                "timeline": [],
                "skipped": [],
                "ai_note": "У тебя нет сохранённых событий на этот день. Свайпни пару карточек!" if body.lang == "ru" else "You have no saved events for this day. Swipe some cards!",
            }

        # ── 3. Fetch preference profile ──────────────────────────────────
        pref_rows = await conn.fetch("""
            SELECT e.category, s.direction, COUNT(*) as cnt
            FROM user_swipes s
            JOIN events e ON e.id = s.event_id
            WHERE s.user_id = $1
            GROUP BY e.category, s.direction
        """, user_id)

    # Build preference dict
    liked: dict[str, int] = {}
    disliked: dict[str, int] = {}
    for row in pref_rows:
        cat = row["category"] or "Other"
        if row["direction"] == "right":
            liked[cat] = row["cnt"]
        else:
            disliked[cat] = row["cnt"]

    # ── 4. Build events data for Gemini ──────────────────────────────────
    def _extract_title(title_jsonb, lang: str) -> str:
        if isinstance(title_jsonb, dict):
            return title_jsonb.get(lang) or title_jsonb.get("en") or title_jsonb.get("ru") or str(title_jsonb)
        if isinstance(title_jsonb, str):
            try:
                parsed = json.loads(title_jsonb)
                if isinstance(parsed, dict):
                    return parsed.get(lang) or parsed.get("en") or parsed.get("ru") or title_jsonb
            except (json.JSONDecodeError, TypeError):
                pass
            return title_jsonb
        return str(title_jsonb)

    events_data = []
    for row in events_rows:
        vlat = row["venue_lat"]
        vlng = row["venue_lng"]
        cat = (row["category"] or "Other").lower()
        dist = _road_km(body.lat, body.lng, vlat, vlng) if vlat and vlng else None

        events_data.append({
            "id": str(row["id"]),
            "title": _extract_title(row["title"], body.lang),
            "category": row["category"] or "Other",
            "time": (row["event_time"] or "")[:5] if row["event_time"] else "TBD",
            "duration_min": DEFAULT_DURATION.get(cat, 60),
            "location": row["location_name"] or "",
            "coords": {"lat": vlat, "lng": vlng} if vlat and vlng else None,
            "distance_from_user_km": dist,
            "price_thb": row["price_thb"] or 0,
        })

    # ── 5. Build venue-to-venue distance matrix ──────────────────────────
    distance_matrix: dict[str, dict] = {}
    coords_events = [e for e in events_data if e["coords"]]

    for i, ea in enumerate(coords_events):
        for j, eb in enumerate(coords_events):
            if i == j:
                continue
            key = f"{ea['id']}→{eb['id']}"
            dist = _road_km(
                ea["coords"]["lat"], ea["coords"]["lng"],
                eb["coords"]["lat"], eb["coords"]["lng"],
            )
            distance_matrix[key] = {
                "km": dist,
                "min": _travel_min(dist),
            }

    # ── 6. Assemble Gemini payload ───────────────────────────────────────
    gemini_input = {
        "user": {
            "name": user_row["first_name"] or "Friend",
            "gender": user_row["gender"] or "unknown",
            "mood": user_row["mood"] or "explore",
            "location": {"lat": body.lat, "lng": body.lng},
            "preferences": {
                "liked": liked,
                "disliked": disliked,
            },
        },
        "target_date": body.date,
        "language": body.lang,
        "events": events_data,
        "distance_matrix": distance_matrix,
    }

    # ── 6.5. Check Cache ─────────────────────────────────────────────────
    gemini_input_str = json.dumps(gemini_input, sort_keys=True, ensure_ascii=False)
    input_hash = hashlib.sha256(gemini_input_str.encode("utf-8")).hexdigest()

    cached_row = await pool.fetchrow("""
        SELECT input_hash, plan_json
        FROM vibe_pilot_cache
        WHERE user_id = $1 AND target_date = $2
    """, user_id, target_date)

    plan = None
    if cached_row and cached_row["input_hash"] == input_hash:
        logger.info("Vibe Pilot: Cache HIT for user %s, date %s", user_id, target_date)
        plan = json.loads(cached_row["plan_json"])

    if not plan:
        # ── 7. Call Gemini with retry + model cascade ────────────────────────
        settings = get_settings()
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        user_prompt = (
            f"Plan the optimal day for {body.date}. "
            f"Language: {'Russian' if body.lang == 'ru' else 'English'}.\n\n"
            f"Input data:\n{json.dumps(gemini_input, ensure_ascii=False, indent=2)}"
        )

        last_error = None

        for model_name, max_attempts in GEMINI_CASCADE:
            # Build config per model — only 2.5+ supports thinking
            if "2.5" in model_name or "3" in model_name:
                gen_config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=16384,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=4096,
                    ),
                )
            else:
                gen_config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=16384,
                    response_mime_type="application/json",
                )

            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(
                        "Vibe Pilot: calling %s (attempt %d/%d)",
                        model_name, attempt, max_attempts,
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=user_prompt,
                        config=gen_config,
                    )

                    raw_text = response.text.strip()
                    if raw_text.startswith("```"):
                        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3].strip()

                    plan = json.loads(raw_text)
                    logger.info("Vibe Pilot: success with %s on attempt %d", model_name, attempt)
                    break

                except json.JSONDecodeError as exc:
                    last_error = exc
                    logger.warning(
                        "Vibe Pilot: %s attempt %d — invalid JSON: %s",
                        model_name, attempt, str(exc)[:200],
                    )
                    break  # JSON error → next model

                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Vibe Pilot: %s attempt %d — %s",
                        model_name, attempt, str(exc)[:200],
                    )
                    if attempt < max_attempts:
                        continue  # Retry immediately, no delay
                    break  # Exhausted retries → next model

            if plan is not None:
                break

        if plan is None:
            logger.error("Vibe Pilot: all models failed. Last error: %s", last_error)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI planner is temporarily unavailable. Please try again.",
            )

        # Save to cache using pool to avoid holding connection during Gemini generation
        await pool.execute("""
            INSERT INTO vibe_pilot_cache (user_id, target_date, input_hash, plan_json)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, target_date)
            DO UPDATE SET input_hash = EXCLUDED.input_hash, plan_json = EXCLUDED.plan_json, created_at = timezone('utc', now())
        """, user_id, target_date, json.dumps(plan, ensure_ascii=False))

    # ── 8. Enrich timeline with full event data ──────────────────────────
    events_by_id = {e["id"]: e for e in events_data}

    for item in plan.get("timeline", []):
        ev = events_by_id.get(item.get("event_id"))
        if ev:
            item["title"] = ev["title"]
            item["location"] = ev["location"]
            item["lat"] = ev["coords"]["lat"] if ev["coords"] else None
            item["lng"] = ev["coords"]["lng"] if ev["coords"] else None
            item["category"] = ev["category"]
            item["price_thb"] = ev["price_thb"]

    for item in plan.get("skipped", []):
        ev = events_by_id.get(item.get("event_id"))
        if ev:
            item["title"] = ev["title"]
            item["time"] = ev["time"]

    # ── 9. Build final response ──────────────────────────────────────────
    total_travel = sum(
        item.get("travel_from_previous_km", 0)
        for item in plan.get("timeline", [])
    )

    return {
        "plan_name": plan.get("plan_name", "Your Day Plan"),
        "date": body.date,
        "total_events": len(plan.get("timeline", [])),
        "total_travel_km": round(total_travel, 1),
        "timeline": plan.get("timeline", []),
        "skipped": plan.get("skipped", []),
        "ai_note": plan.get("ai_note", ""),
    }
