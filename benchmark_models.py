"""
Benchmark: DeepSeek-Reasoner vs DeepSeek-Chat vs Kimi-for-Coding
Real Vibe Pilot payload with 20 real events from Koh Phangan.
"""
import asyncio
import json
import time
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

DEEPSEEK_API_KEY = "sk-26727fc3f68848caa3c00d638298aef3"
KIMI_CODE_API_KEY = "sk-kimi-L8LbZ5q9MDPyRTTQopIOwEYgGcQhNWlxvPX3FhLXQsaeK4qaBtIUNKcEiFCQhRtj"

# ── System prompt (same as production) ──────────────────────────────
SYSTEM_PROMPT = """You are Vibe Pilot 🧭 — an AI day planner for travelers on Koh Phangan island, Thailand.

TASK: Build an optimized day plan from the user's liked events.

RULES:
1. RESOLVE TIME CONFLICTS: When events overlap, pick the best one based on proximity, preference, gender relevance, price, and route.
2. ROUTE OPTIMIZATION: Consider sequential travel from previous event.
3. TIME GAPS: Ensure at least (travel_time + 15 min buffer) between events.
4. DURATION: Use the provided duration_min for each event. Never overlap events temporally.
5. Be encouraging, friendly in your reasons. Keep them concise — 1-2 sentences max.
6. Respond in the specified language.

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

# ── Real payload from production DB (20 events, April 4, 2026) ──────
PAYLOAD = {
    "user": {
        "name": "Evgeniy",
        "gender": "male",
        "mood": "explore",
        "location": {"lat": 9.74, "lng": 100.0},
        "preferences": {
            "liked": {"yoga": 8, "fitness": 5, "event": 12, "meditation": 3, "dance": 2, "workshop": 1},
            "disliked": {"pilates": 2, "circle": 1}
        }
    },
    "target_date": "2026-04-04",
    "language": "ru",
    "events": [
        {"id": "17954", "title": "Клуб 5:55 Утра: Пробуждение Сангхи — Движение", "category": "event", "time": "05:55", "duration_min": 60, "location": "HEXAGON Garden Temple", "coords": {"lat": 9.7588596, "lng": 99.9695684}, "distance_from_user_km": 3.5, "price_thb": 0},
        {"id": "17955", "title": "Медитация Благодарности: Мать-Земля", "category": "meditation", "time": "06:22", "duration_min": 60, "location": "Baan Tai", "coords": {"lat": 9.7198806, "lng": 100.0471549}, "distance_from_user_km": 5.6, "price_thb": 0},
        {"id": "17956", "title": "Динамическая медитация Ошо", "category": "event", "time": "07:00", "duration_min": 75, "location": "Samma Karuna", "coords": {"lat": 9.766555, "lng": 99.96271}, "distance_from_user_km": 4.6, "price_thb": 0},
        {"id": "17957", "title": "Круг Островных Братьев", "category": "circle", "time": "07:45", "duration_min": 60, "location": "Flamingo Beach Bar", "coords": {"lat": 9.756052, "lng": 99.963255}, "distance_from_user_km": 4.3, "price_thb": 0},
        {"id": "17958", "title": "Кроссфит Мобильность: Раскройте Тело", "category": "fitness", "time": "08:00", "duration_min": 75, "location": "Podium Gym", "coords": {"lat": 9.712503, "lng": 99.990284}, "distance_from_user_km": 3.2, "price_thb": 0},
        {"id": "17961", "title": "Творческий Виньяса Флоу", "category": "yoga", "time": "08:00", "duration_min": 75, "location": "Orion Healing Centre", "coords": {"lat": 9.751892, "lng": 99.966052}, "distance_from_user_km": 4.0, "price_thb": 0},
        {"id": "17959", "title": "Пауэр-виньяса с Фа", "category": "event", "time": "08:00", "duration_min": 75, "location": "Breath Body Balance", "coords": {"lat": 9.7793412, "lng": 99.9666412}, "distance_from_user_km": 5.5, "price_thb": 0},
        {"id": "17962", "title": "Метта: Медитация Любящей Доброты", "category": "meditation", "time": "08:30", "duration_min": 60, "location": "Arcana Wellness Village", "coords": {"lat": 9.773565, "lng": 99.9804348}, "distance_from_user_km": 4.2, "price_thb": 0},
        {"id": "17963", "title": "Аштанга-Йога: Полная Первичная Серия", "category": "yoga", "time": "08:30", "duration_min": 90, "location": "The Yoga Retreat", "coords": {"lat": 9.7859471, "lng": 99.983017}, "distance_from_user_km": 5.3, "price_thb": 0},
        {"id": "18034", "title": "Класс Муай Тай", "category": "event", "time": "08:30", "duration_min": 75, "location": "Worawut Muay Thai", "coords": {"lat": 9.7087649, "lng": 99.9981128}, "distance_from_user_km": 3.5, "price_thb": 0},
        {"id": "17965", "title": "Утренняя Сауна и Ледяная Купель", "category": "event", "time": "08:30", "duration_min": 60, "location": "HEXAGON Garden Temple", "coords": {"lat": 9.7588596, "lng": 99.9695684}, "distance_from_user_km": 3.5, "price_thb": 0},
        {"id": "17966", "title": "Командная Тренировка КроссФит с Кейт", "category": "fitness", "time": "09:15", "duration_min": 75, "location": "Podium Gym", "coords": {"lat": 9.712503, "lng": 99.990284}, "distance_from_user_km": 3.2, "price_thb": 0},
        {"id": "17967", "title": "Функциональный буткемп с Дианой Б.", "category": "event", "time": "09:30", "duration_min": 60, "location": "Podium Gym", "coords": {"lat": 9.712503, "lng": 99.990284}, "distance_from_user_km": 3.2, "price_thb": 0},
        {"id": "17968", "title": "Утренняя Йога в Ананде", "category": "yoga", "time": "09:30", "duration_min": 75, "location": "Ananda Yoga & Detox Center", "coords": {"lat": 9.7461557, "lng": 99.9761932}, "distance_from_user_km": 2.8, "price_thb": 0},
        {"id": "17969", "title": "Силовой Час на Реформере", "category": "pilates", "time": "09:45", "duration_min": 60, "location": "Podium Gym", "coords": {"lat": 9.712503, "lng": 99.990284}, "distance_from_user_km": 3.2, "price_thb": 0},
        {"id": "17973", "title": "Бранч Богинь ИИ: Мастер-класс для Женщин", "category": "workshop", "time": "10:00", "duration_min": 90, "location": "Chaloklum", "coords": {"lat": 9.7868687, "lng": 100.0042816}, "distance_from_user_km": 5.2, "price_thb": 0},
        {"id": "17972", "title": "Осознанный Утренний Заплыв на Хаад Чао Пхао", "category": "event", "time": "10:00", "duration_min": 60, "location": "Phangan Cabana Resort", "coords": {"lat": 9.76413, "lng": 99.9629772}, "distance_from_user_km": 4.5, "price_thb": 0},
        {"id": "17977", "title": "Кундалини-Йога: Пробуждение Внутренней Энергии", "category": "yoga", "time": "10:00", "duration_min": 75, "location": "ETHOS Wholefood Cafe & Shala", "coords": {"lat": 9.7563293, "lng": 99.9659748}, "distance_from_user_km": 4.0, "price_thb": 0},
        {"id": "17974", "title": "Хатха Флоу: Практика Среднего Уровня", "category": "yoga", "time": "10:00", "duration_min": 75, "location": "Soulscape", "coords": {"lat": 9.7045243, "lng": 100.014893}, "distance_from_user_km": 4.3, "price_thb": 0},
        {"id": "17970", "title": "Деконструкция Контакта: Танец Осознанности", "category": "dance", "time": "10:00", "duration_min": 75, "location": "Shivari", "coords": {"lat": 9.7852771, "lng": 99.974277}, "distance_from_user_km": 5.7, "price_thb": 0}
    ],
    "distance_matrix": {
        "17954→17958": {"km": 6.2, "min": 15},
        "17958→17966": {"km": 0.0, "min": 1},
        "17966→17968": {"km": 4.0, "min": 10},
        "17961→17965": {"km": 1.0, "min": 3},
        "17956→17961": {"km": 1.7, "min": 4},
        "17968→17977": {"km": 1.4, "min": 3},
        "17977→17970": {"km": 3.3, "min": 8},
        "17958→17967": {"km": 0.0, "min": 1},
        "17965→17972": {"km": 0.9, "min": 2},
        "17963→17973": {"km": 2.3, "min": 6}
    }
}

USER_PROMPT = (
    "Plan the optimal day for 2026-04-04. "
    "Language: Russian.\n\n"
    f"Input data:\n{json.dumps(PAYLOAD, ensure_ascii=False, indent=2)}"
)


async def benchmark_deepseek(model_name: str) -> dict:
    """Test a DeepSeek model (reasoner or chat) via OpenAI SDK."""
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    t0 = time.time()
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ]
        )
        elapsed = time.time() - t0
        raw = response.choices[0].message.content or ""
        # Count reasoning tokens if available
        reasoning_len = 0
        if hasattr(response.choices[0].message, 'reasoning_content') and response.choices[0].message.reasoning_content:
            reasoning_len = len(response.choices[0].message.reasoning_content)
        
        return {
            "model": model_name,
            "time_sec": round(elapsed, 2),
            "raw_len": len(raw),
            "reasoning_chars": reasoning_len,
            "raw": raw,
            "error": None
        }
    except Exception as e:
        return {"model": model_name, "time_sec": round(time.time() - t0, 2), "raw_len": 0, "reasoning_chars": 0, "raw": "", "error": str(e)}


async def benchmark_kimi() -> dict:
    """Test Kimi-for-coding via Anthropic SDK."""
    client = AsyncAnthropic(
        api_key=KIMI_CODE_API_KEY,
        base_url="https://api.kimi.com/coding/",
        default_headers={"User-Agent": "ClaudeCode/1.0"}
    )
    t0 = time.time()
    try:
        response = await client.messages.create(
            model="kimi-for-coding",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_PROMPT}]
        )
        elapsed = time.time() - t0
        raw = response.content[0].text.strip()
        return {
            "model": "kimi-for-coding",
            "time_sec": round(elapsed, 2),
            "raw_len": len(raw),
            "reasoning_chars": 0,
            "raw": raw,
            "error": None
        }
    except Exception as e:
        return {"model": "kimi-for-coding", "time_sec": round(time.time() - t0, 2), "raw_len": 0, "reasoning_chars": 0, "raw": "", "error": str(e)}


def parse_plan(raw: str) -> dict | None:
    """Try to parse JSON from raw response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def print_result(result: dict):
    model = result["model"]
    print(f"\n{'='*70}")
    print(f"  🤖 Model: {model}")
    print(f"  ⏱  Time:  {result['time_sec']}s")
    print(f"  📏 Output: {result['raw_len']} chars")
    if result["reasoning_chars"]:
        print(f"  🧠 Reasoning: {result['reasoning_chars']} chars (internal thinking)")
    if result["error"]:
        print(f"  ❌ ERROR: {result['error']}")
        return
    
    plan = parse_plan(result["raw"])
    if not plan:
        print(f"  ❌ JSON PARSE FAILED!")
        print(f"  Raw preview: {result['raw'][:200]}...")
        return
    
    print(f"  ✅ Valid JSON!")
    print(f"  📝 Plan: {plan.get('plan_name', '?')}")
    timeline = plan.get("timeline", [])
    skipped = plan.get("skipped", [])
    print(f"  📅 Events in timeline: {len(timeline)}")
    print(f"  ⏭  Skipped events: {len(skipped)}")
    print(f"  💬 AI Note: {plan.get('ai_note', '?')[:120]}...")
    
    print(f"\n  Timeline:")
    for item in timeline:
        eid = item.get("event_id", "?")
        st = item.get("start_time", "?")
        et = item.get("end_time", "?")
        travel = item.get("travel_from_previous_km", 0)
        reason = item.get("reason", "")[:60]
        # find event title
        ev = next((e for e in PAYLOAD["events"] if e["id"] == str(eid)), None)
        title = ev["title"][:40] if ev else "?"
        print(f"    {item.get('order', '?')}. [{st}-{et}] {title}  🛵{travel}km — {reason}")


async def main():
    print("🏁 VIBE PILOT MODEL BENCHMARK")
    print(f"   Events: {len(PAYLOAD['events'])} real events from 2026-04-04")
    print(f"   Payload size: {len(USER_PROMPT)} chars")
    print("   Running all 3 models IN PARALLEL...\n")

    results = await asyncio.gather(
        benchmark_deepseek("deepseek-reasoner"),
        benchmark_deepseek("deepseek-chat"),
        benchmark_kimi(),
    )

    # Sort by time
    results.sort(key=lambda r: r["time_sec"])

    for r in results:
        print_result(r)

    # Summary table
    print(f"\n\n{'='*70}")
    print("  📊 SUMMARY TABLE")
    print(f"  {'Model':<25} {'Time':>8} {'JSON':>6} {'Timeline':>10} {'Skipped':>9}")
    print(f"  {'-'*25} {'-'*8} {'-'*6} {'-'*10} {'-'*9}")
    for r in results:
        plan = parse_plan(r["raw"])
        tl = len(plan.get("timeline", [])) if plan else 0
        sk = len(plan.get("skipped", [])) if plan else 0
        valid = "✅" if plan else "❌"
        print(f"  {r['model']:<25} {r['time_sec']:>6.1f}s {valid:>6} {tl:>10} {sk:>9}")

    fastest = results[0]
    slowest = results[-1]
    print(f"\n  🏆 Winner: {fastest['model']} ({fastest['time_sec']}s)")
    print(f"  🐢 Slowest: {slowest['model']} ({slowest['time_sec']}s)")
    print(f"  📈 Speed diff: {slowest['time_sec'] / fastest['time_sec']:.1f}x")


if __name__ == "__main__":
    asyncio.run(main())
