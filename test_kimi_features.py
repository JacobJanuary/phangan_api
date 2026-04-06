import asyncio
import json
import os
import math

from anthropic import AsyncAnthropic

KIMI_API_KEY = "sk-kimi-L8LbZ5q9MDPyRTTQopIOwEYgGcQhNWlxvPX3FhLXQsaeK4qaBtIUNKcEiFCQhRtj"

# ── Haversine & routing mocks ────────────────────────────────────────────────
def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _road_km(lat1, lng1, lat2, lng2):
    return round(_haversine_km(lat1, lng1, lat2, lng2) * 1.4, 1)

def _travel_min(dist_km):
    return max(1, math.ceil(dist_km / 25 * 60))

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

OUTPUT: Return ONLY valid raw JSON (strictly no markdown formatting, no ```json wrappers), matching this format:
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

async def test_gender(client):
    print("--- 1. Testing Gender Detection ---")
    names = ["Evgeniy", "Anna", "Alex", "Sirinya"]
    for name in names:
        prompt = f"Determine the most likely gender for the first name '{name}'. Reply strictly with either 'male' or 'female'."
        response = await client.messages.create(
            model="kimi-for-coding",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        print(f"Name: {name} => Kimi Output: {response.content[0].text.strip()}")

async def test_vibe_pilot(client):
    print("\n--- 2. Testing Vibe Pilot (AI Planner) ---")
    
    # Mock some Koh Phangan events with conflicts
    events_data = [
        {
            "id": "100", "title": "Morning Yoga Flow", "category": "sport", "time": "08:00", "duration_min": 90,
            "location": "Srithanu Beach", "coords": {"lat": 9.75, "lng": 99.96}, "price_thb": 300
        },
        {
            "id": "101", "title": "Ice Bath & Breathwork", "category": "chill", "time": "08:30", "duration_min": 60,
            "location": "Zen Hub", "coords": {"lat": 9.76, "lng": 99.97}, "price_thb": 400
        },
        {
            "id": "102", "title": "Ecstatic Dance", "category": "party", "time": "11:00", "duration_min": 180,
            "location": "Pyramid", "coords": {"lat": 9.77, "lng": 99.98}, "price_thb": 500
        },
        {
            "id": "103", "title": "Sunset Cacao Ceremony", "category": "spiritual", "time": "17:30", "duration_min": 120,
            "location": "AUM Sound Healing", "coords": {"lat": 9.72, "lng": 100.01}, "price_thb": 600
        }
    ]

    distance_matrix = {}
    for i, ea in enumerate(events_data):
        for j, eb in enumerate(events_data):
            if i == j: continue
            dist = _road_km(ea["coords"]["lat"], ea["coords"]["lng"], eb["coords"]["lat"], eb["coords"]["lng"])
            distance_matrix[f"{ea['id']}→{eb['id']}"] = {"km": dist, "min": _travel_min(dist)}

    gemini_input = {
        "user": {
            "name": "Tom",
            "gender": "male",
            "mood": "explore",
            "location": {"lat": 9.70, "lng": 100.00}, # Somewhere in Thong Sala
            "preferences": {"liked": {"sport": 10, "party": 15}, "disliked": {"chill": 2}}
        },
        "target_date": "2026-03-20",
        "language": "ru",
        "events": events_data,
        "distance_matrix": distance_matrix
    }

    user_prompt = (
        f"Plan the optimal day for 2026-03-20. "
        f"Language: Russian.\n\n"
        f"Input data:\n{json.dumps(gemini_input, ensure_ascii=False, indent=2)}"
    )

    print("Sending Vibe Pilot prompt to Kimi... (Waiting for response)")
    try:
        response = await client.messages.create(
            model="kimi-for-coding",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        raw_text = response.content[0].text.strip()
        print("\nRAW OUTPUT FROM KIMI:")
        print(raw_text)
        
        # Test parsing
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()
            
        plan = json.loads(raw_text)
        print("\n✅ Successfully parsed as JSON! Timeline has", len(plan.get("timeline", [])), "events.")
        
    except Exception as e:
        print("\n❌ Failed to generate or parse Vibe Pilot output:", e)


async def main():
    client = AsyncAnthropic(
        api_key=KIMI_API_KEY,
        base_url="https://api.kimi.com/coding/",
        default_headers={"User-Agent": "ClaudeCode/1.0"}
    )
    
    await test_gender(client)
    await test_vibe_pilot(client)

if __name__ == "__main__":
    asyncio.run(main())
