"""
Re-encode the 9 failing images through Pillow to create clean VP8 WebP files.
Backs up originals, overwrites with re-encoded versions.
"""
from PIL import Image
import os
import shutil

MEDIA_DIR = "/home/ubuntu/Phangan/TG_parcer/media"
BACKUP_DIR = "/home/ubuntu/Phangan/TG_parcer/media_backup_fail9"

FAIL = [
    "event_chill_be5a35bf.webp",
    "event_chill_acd73521.webp",
    "event_chill_b33af15c.webp",
    "event_chill_96d7240e.webp",
    "event_chill_93a3745d.webp",
    "event_chill_45e26bf5.webp",
    "event_chill_d2d40b2b.webp",
    "event_chill_e303f4d4.webp",
    "event_chill_c0479161.webp",
]

os.makedirs(BACKUP_DIR, exist_ok=True)

for fname in FAIL:
    src = os.path.join(MEDIA_DIR, fname)
    bak = os.path.join(BACKUP_DIR, fname)
    
    # Backup original
    shutil.copy2(src, bak)
    
    old_size = os.path.getsize(src)
    
    # Re-encode: open → save with explicit WebP VP8 lossy
    im = Image.open(src)
    im = im.convert("RGB")  # Force RGB, drop any weird profile
    im.save(src, "WEBP", quality=85, method=4)
    
    new_size = os.path.getsize(src)
    print(f"✅ {fname}: {old_size} → {new_size} bytes")

print(f"\nDone! Originals backed up to {BACKUP_DIR}")
print("Re-check https://phangan.fastpump.fun/image_audit.html to verify fix.")
