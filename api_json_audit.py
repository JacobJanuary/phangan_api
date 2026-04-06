"""
Check the actual JSON response from the API endpoint /api/v1/events
to see what image_path values look like for events that the frontend sees.
"""
import asyncio
import aiohttp
import json

API_BASE = "http://127.0.0.1:62537"

async def main():
    # First, we need a valid token. Let's simulate auth.
    # Actually, let's just check what the events endpoint returns without auth
    # or check the raw DB output that the API serializes
    
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        # Try fetching events without auth to see the response format
        async with session.get(f"{API_BASE}/api/v1/events?limit=200&lang=ru") as resp:
            status = resp.status
            body = await resp.text()
            print(f"Status: {status}")
            if status != 200:
                print(f"Response: {body[:500]}")
                print("\nNeed auth token. Let's check the API router to understand the response format instead.")
                return
            
            data = json.loads(body)
            events = data.get('events', data if isinstance(data, list) else [])
            
            print(f"Total events in response: {len(events)}")
            
            # Categorize image_path values
            null_count = 0
            empty_count = 0
            valid_count = 0
            weird = []
            
            for ev in events:
                img = ev.get('image_path')
                title = ev.get('title', '?')
                if isinstance(title, dict):
                    title = title.get('ru', title.get('en', '?'))
                
                if img is None:
                    null_count += 1
                    weird.append(f"NULL image_path | title={str(title)[:50]}")
                elif img == '' or img == 'null' or img == '""' or img == '{}':
                    empty_count += 1
                    weird.append(f"EMPTY/WEIRD image_path='{img}' | title={str(title)[:50]}")
                elif isinstance(img, str) and len(img) > 0:
                    valid_count += 1
                else:
                    weird.append(f"UNEXPECTED type={type(img).__name__} value={str(img)[:100]} | title={str(title)[:50]}")
            
            print(f"\n✅ Valid image_path: {valid_count}")
            print(f"❌ Null image_path: {null_count}")
            print(f"⚠️  Empty/weird image_path: {empty_count}")
            
            if weird:
                print(f"\n{'='*80}")
                print(f"PROBLEMATIC EVENTS ({len(weird)}):")
                for w in weird[:50]:
                    print(f"  {w}")

            # Also print first 3 valid ones for comparison
            print(f"\n--- Sample valid events ---")
            count = 0
            for ev in events:
                img = ev.get('image_path')
                if img and isinstance(img, str) and len(img) > 3:
                    title = ev.get('title', '?')
                    if isinstance(title, dict):
                        title = title.get('ru', '?')
                    print(f"  title={str(title)[:40]} | image_path={img}")
                    count += 1
                    if count >= 3:
                        break

asyncio.run(main())
