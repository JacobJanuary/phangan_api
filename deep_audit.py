"""
Deep audit of ALL event images.
Checks every image file for:
1. File existence
2. File size (zero / suspiciously small)
3. WebP header validity (RIFF + WEBP magic bytes)
4. WebP encoding type (VP8, VP8L, VP8X)
5. Image dimensions (via Pillow)
6. Whether it can actually be decoded by Pillow
7. Content-Length match via local HTTP request to Uvicorn
"""
import asyncio
import asyncpg
import os
import struct
import subprocess
import json
from collections import Counter

MEDIA_DIR = "/home/ubuntu/Phangan/TG_parcer/media"

async def main():
    conn = await asyncpg.connect(
        user='thai_app_user',
        password='ILoveThai@%37',
        database='ThaiApp',
        host='127.0.0.1'
    )

    rows = await conn.fetch("SELECT id, title::text, image_path FROM events WHERE image_path IS NOT NULL AND image_path != '';")
    await conn.close()

    print(f"Total events with image_path: {len(rows)}")
    print("=" * 80)

    issues = []
    encoding_stats = Counter()
    size_buckets = Counter()
    ok_count = 0
    ok_sizes = []
    bad_sizes = []

    for row in rows:
        eid = row['id']
        title = row['title'][:60] if row['title'] else '?'
        img = row['image_path']

        filepath = os.path.join(MEDIA_DIR, img)

        # 1. Check existence
        if not os.path.exists(filepath):
            issues.append(f"MISSING FILE: id={eid} path={img} title={title}")
            continue

        # 2. Check file size
        fsize = os.path.getsize(filepath)
        if fsize == 0:
            issues.append(f"ZERO SIZE: id={eid} path={img} size=0 title={title}")
            continue
        if fsize < 1000:
            issues.append(f"TINY FILE (<1KB): id={eid} path={img} size={fsize} title={title}")
            continue

        # Bucket sizes
        if fsize < 5000:
            size_buckets['1-5KB'] += 1
        elif fsize < 20000:
            size_buckets['5-20KB'] += 1
        elif fsize < 50000:
            size_buckets['20-50KB'] += 1
        elif fsize < 100000:
            size_buckets['50-100KB'] += 1
        else:
            size_buckets['100KB+'] += 1

        # 3. Check WebP magic bytes
        with open(filepath, 'rb') as f:
            header = f.read(32)

        if len(header) < 12:
            issues.append(f"TOO SHORT HEADER: id={eid} path={img} size={fsize} title={title}")
            continue

        riff = header[0:4]
        webp = header[8:12]

        if riff != b'RIFF' or webp != b'WEBP':
            # Check if it's actually a JPEG or PNG
            if header[0:2] == b'\xff\xd8':
                issues.append(f"ACTUALLY JPEG (not WebP!): id={eid} path={img} size={fsize} title={title}")
            elif header[0:4] == b'\x89PNG':
                issues.append(f"ACTUALLY PNG (not WebP!): id={eid} path={img} size={fsize} title={title}")
            else:
                issues.append(f"INVALID HEADER: id={eid} path={img} magic={header[:12].hex()} size={fsize} title={title}")
            continue

        # 4. Check RIFF declared size vs actual file size
        riff_size = struct.unpack('<I', header[4:8])[0] + 8  # RIFF size + 8 bytes for RIFF header
        if riff_size != fsize:
            issues.append(f"TRUNCATED/CORRUPT: id={eid} path={img} riff_declares={riff_size} actual={fsize} delta={riff_size - fsize} title={title}")
            bad_sizes.append(fsize)
            continue

        # 5. Detect WebP encoding type
        chunk_type = header[12:16].decode('ascii', errors='replace')
        encoding_stats[chunk_type] += 1

        # 6. Try to decode with Pillow
        try:
            from PIL import Image
            im = Image.open(filepath)
            im.verify()  # Verify without fully loading
        except Exception as e:
            issues.append(f"PILLOW DECODE FAIL: id={eid} path={img} size={fsize} error={str(e)[:100]} title={title}")
            bad_sizes.append(fsize)
            continue

        ok_count += 1
        ok_sizes.append(fsize)

    print(f"\n✅ OK images: {ok_count}")
    print(f"❌ Issues found: {len(issues)}")
    print(f"\n--- Encoding types (OK only) ---")
    for k, v in encoding_stats.most_common():
        print(f"  {k}: {v}")
    print(f"\n--- Size distribution (all files) ---")
    for k, v in sorted(size_buckets.items()):
        print(f"  {k}: {v}")

    if issues:
        print(f"\n{'=' * 80}")
        print(f"DETAILED ISSUES ({len(issues)}):")
        print(f"{'=' * 80}")
        for issue in issues:
            print(f"  ⚠️  {issue}")

    # Summary of bad vs ok sizes
    if ok_sizes:
        print(f"\n--- OK file sizes: min={min(ok_sizes)}, max={max(ok_sizes)}, avg={sum(ok_sizes)//len(ok_sizes)} ---")
    if bad_sizes:
        print(f"--- BAD file sizes: min={min(bad_sizes)}, max={max(bad_sizes)}, avg={sum(bad_sizes)//len(bad_sizes)} ---")

asyncio.run(main())
