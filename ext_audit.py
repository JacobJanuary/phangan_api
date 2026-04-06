import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(user='thai_app_user', password='ILoveThai@%37', database='ThaiApp', host='127.0.0.1')
    
    # Count by extension
    webp = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path LIKE '%.webp';")
    jpg = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path LIKE '%.jpg';")
    png = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path LIKE '%.png';")
    other = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path IS NOT NULL AND image_path != '' AND image_path NOT LIKE '%.webp' AND image_path NOT LIKE '%.jpg' AND image_path NOT LIKE '%.png';")
    null_count = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path IS NULL OR image_path = '';")
    
    print(f"By extension:")
    print(f"  .webp: {webp}")
    print(f"  .jpg:  {jpg}")
    print(f"  .png:  {png}")
    print(f"  other: {other}")
    print(f"  null:  {null_count}")
    
    # Show sample .jpg events
    if jpg > 0:
        rows = await conn.fetch("SELECT title::text, image_path FROM events WHERE image_path LIKE '%.jpg' LIMIT 5;")
        print(f"\nSample .jpg events:")
        for r in rows:
            print(f"  {r['title'][:50]} | {r['image_path']}")
    
    # Show sample 'other' events
    if other > 0:
        rows = await conn.fetch("SELECT title::text, image_path FROM events WHERE image_path IS NOT NULL AND image_path != '' AND image_path NOT LIKE '%.webp' AND image_path NOT LIKE '%.jpg' AND image_path NOT LIKE '%.png' LIMIT 10;")
        print(f"\nSample 'other' events:")
        for r in rows:
            print(f"  {r['title'][:50]} | {r['image_path']}")
    
    # Check today's events specifically (what the user is seeing)
    today_total = await conn.fetchval("SELECT COUNT(*) FROM events WHERE event_date = CURRENT_DATE;")
    today_webp = await conn.fetchval("SELECT COUNT(*) FROM events WHERE event_date = CURRENT_DATE AND image_path LIKE '%.webp';")
    today_jpg = await conn.fetchval("SELECT COUNT(*) FROM events WHERE event_date = CURRENT_DATE AND image_path LIKE '%.jpg';")
    today_null = await conn.fetchval("SELECT COUNT(*) FROM events WHERE event_date = CURRENT_DATE AND (image_path IS NULL OR image_path = '');")
    
    print(f"\nTODAY's events:")
    print(f"  Total: {today_total}")
    print(f"  .webp: {today_webp}")
    print(f"  .jpg:  {today_jpg}")
    print(f"  null:  {today_null}")
    
    # Show today's events with their image_path
    rows = await conn.fetch("SELECT title::text, image_path, event_time FROM events WHERE event_date = CURRENT_DATE ORDER BY event_time;")
    print(f"\nAll of today's events:")
    for r in rows:
        title = r['title'][:50] if r['title'] else '?'
        img = r['image_path'] or 'NULL'
        print(f"  {r['event_time'] or 'TBD'} | {title} | {img}")
    
    await conn.close()

asyncio.run(main())
