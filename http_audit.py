"""
HTTP-level audit: Request EVERY image via the local Uvicorn endpoint
and check for failures, truncation, or weird responses.
Also check for patterns in the failures.
"""
import asyncio
import asyncpg
import aiohttp
import time

UVICORN_BASE = "http://127.0.0.1:62537/api/media/"

async def check_image(session, img_path, eid, title):
    url = UVICORN_BASE + img_path
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            status = resp.status
            ct = resp.headers.get('content-type', '')
            cl = resp.headers.get('content-length', '0')
            body = await resp.read()
            
            if status != 200:
                return {'id': eid, 'img': img_path, 'issue': f'HTTP {status}', 'title': title}
            
            if 'image' not in ct:
                return {'id': eid, 'img': img_path, 'issue': f'Wrong content-type: {ct}', 'title': title}
            
            if len(body) < 1000:
                return {'id': eid, 'img': img_path, 'issue': f'Tiny response body: {len(body)} bytes', 'title': title}
            
            expected = int(cl)
            if expected > 0 and len(body) != expected:
                return {'id': eid, 'img': img_path, 'issue': f'Truncated: expected={expected} got={len(body)}', 'title': title}
            
            # Check RIFF header in response body
            if body[:4] != b'RIFF' or body[8:12] != b'WEBP':
                return {'id': eid, 'img': img_path, 'issue': f'Response not valid WebP: {body[:16].hex()}', 'title': title}
            
            return None  # OK
    except Exception as e:
        return {'id': eid, 'img': img_path, 'issue': f'Exception: {str(e)[:100]}', 'title': title}

async def main():
    conn = await asyncpg.connect(
        user='thai_app_user',
        password='ILoveThai@%37',
        database='ThaiApp',
        host='127.0.0.1'
    )
    rows = await conn.fetch("SELECT id, title::text, image_path FROM events WHERE image_path IS NOT NULL AND image_path != '';")
    await conn.close()

    print(f"Testing {len(rows)} images via HTTP to Uvicorn...")
    start = time.time()

    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_image(session, row['image_path'], row['id'], row['title'][:60] if row['title'] else '?') for row in rows]
        results = await asyncio.gather(*tasks)

    issues = [r for r in results if r is not None]
    elapsed = time.time() - start

    print(f"\nDone in {elapsed:.1f}s")
    print(f"✅ OK: {len(rows) - len(issues)}")
    print(f"❌ Failed: {len(issues)}")

    if issues:
        print(f"\n{'='*80}")
        print("FAILURES:")
        print(f"{'='*80}")
        for i in issues:
            print(f"  ⚠️  id={i['id']} | {i['img']} | {i['issue']} | {i['title']}")

asyncio.run(main())
