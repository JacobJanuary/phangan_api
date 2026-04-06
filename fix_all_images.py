"""
Re-encode ALL 1585 WebP images through Pillow to ensure WebKit compatibility.
Backs up originals first.
"""
from PIL import Image
import os
import shutil
import time

MEDIA_DIR = "/home/ubuntu/Phangan/TG_parcer/media"
BACKUP_DIR = "/home/ubuntu/Phangan/TG_parcer/media_backup_all"

os.makedirs(BACKUP_DIR, exist_ok=True)

files = [f for f in os.listdir(MEDIA_DIR) if f.endswith('.webp') and os.path.isfile(os.path.join(MEDIA_DIR, f))]
print(f"Found {len(files)} WebP files to re-encode")

start = time.time()
ok = 0
skipped = 0
errors = []

for i, fname in enumerate(sorted(files)):
    src = os.path.join(MEDIA_DIR, fname)
    bak = os.path.join(BACKUP_DIR, fname)
    
    try:
        # Backup (skip if already backed up from earlier run)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
        
        old_size = os.path.getsize(src)
        
        # Re-encode through Pillow
        im = Image.open(src)
        im = im.convert("RGB")
        im.save(src, "WEBP", quality=85, method=4)
        
        new_size = os.path.getsize(src)
        ok += 1
        
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{len(files)} ({ok} OK, {len(errors)} errors)")
    except Exception as e:
        errors.append(f"{fname}: {str(e)[:100]}")

elapsed = time.time() - start
print(f"\nDone in {elapsed:.1f}s")
print(f"✅ Re-encoded: {ok}")
print(f"❌ Errors: {len(errors)}")
if errors:
    for e in errors:
        print(f"  ⚠️  {e}")
print(f"\nOriginals backed up to: {BACKUP_DIR}")
