"""
Compare the 9 FAILING images vs a sample of WORKING images.
Check: file size, WebP chunk type, image dimensions, VP8 bitstream details, 
Pillow decode mode, color profile, and any binary anomalies.
"""
import os
import struct
from PIL import Image

MEDIA_DIR = "/home/ubuntu/Phangan/TG_parcer/media"

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

# Pick some known-working images from same category
OK = [
    "event_chill_501c2d03.webp",
    "event_chill_31892f8f.webp",
    "event_chill_8417bfc2.webp",
    "event_chill_47d3e61d.webp",
    "event_chill_976e71ff.webp",
    "event_chill_e6e2afb8.webp",
    "event_chill_0e2ea252.webp",
    "event_chill_e7e25f9d.webp",
    "event_chill_ebbe0606.webp",
]

def analyze(path, label):
    fp = os.path.join(MEDIA_DIR, path)
    fsize = os.path.getsize(fp)
    
    with open(fp, 'rb') as f:
        data = f.read()
    
    # RIFF header
    riff_size = struct.unpack('<I', data[4:8])[0] + 8
    chunk_fourcc = data[12:16].decode('ascii', errors='replace')
    
    # VP8 bitstream header analysis
    vp8_details = ""
    if chunk_fourcc == 'VP8 ':
        # Lossy VP8
        chunk_size = struct.unpack('<I', data[16:20])[0]
        # VP8 frame header starts at byte 20
        # First 3 bytes: frame tag
        if len(data) > 23:
            frame_tag = data[20] | (data[21] << 8) | (data[22] << 16)
            key_frame = not (frame_tag & 1)
            version = (frame_tag >> 1) & 7
            show_frame = (frame_tag >> 4) & 1
            first_part_size = frame_tag >> 5
            vp8_details = f"key={key_frame} ver={version} show={show_frame} part1_sz={first_part_size}"
            
            if key_frame and len(data) > 29:
                # Key frame has a start code 0x9D 0x01 0x2A followed by width/height
                sc = data[23:26]
                if sc == b'\x9d\x01\x2a':
                    w = struct.unpack('<H', data[26:28])[0] & 0x3FFF
                    h = struct.unpack('<H', data[28:30])[0] & 0x3FFF
                    hscale = data[27] >> 6
                    vscale = data[29] >> 6
                    vp8_details += f" dim={w}x{h} hscale={hscale} vscale={vscale}"
                else:
                    vp8_details += f" BAD_START_CODE={sc.hex()}"
    elif chunk_fourcc == 'VP8L':
        chunk_size = struct.unpack('<I', data[16:20])[0]
        vp8_details = f"lossless chunk_size={chunk_size}"
    elif chunk_fourcc == 'VP8X':
        # Extended format
        flags = struct.unpack('<I', data[16:20])[0]
        has_alpha = bool(flags & (1 << 4))
        has_anim = bool(flags & (1 << 1))
        canvas_w = struct.unpack('<I', data[20:23] + b'\x00')[0] + 1
        canvas_h = struct.unpack('<I', data[23:26] + b'\x00')[0] + 1
        vp8_details = f"VP8X alpha={has_alpha} anim={has_anim} canvas={canvas_w}x{canvas_h}"
    
    # Pillow analysis
    try:
        im = Image.open(fp)
        pil_mode = im.mode
        pil_size = im.size
        pil_info = {k: str(v)[:50] for k, v in im.info.items()}
    except Exception as e:
        pil_mode = f"ERROR: {e}"
        pil_size = (0, 0)
        pil_info = {}
    
    # File creation time
    mtime = os.path.getmtime(fp)
    from datetime import datetime
    mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
    
    print(f"  [{label}] {path}")
    print(f"    size={fsize:>7} | riff={riff_size:>7} | match={'✅' if fsize == riff_size else '❌ MISMATCH'}")
    print(f"    chunk={chunk_fourcc} | {vp8_details}")
    print(f"    pillow: mode={pil_mode} size={pil_size} info={pil_info}")
    print(f"    mtime={mtime_str}")
    return {
        'path': path, 'size': fsize, 'riff': riff_size, 'chunk': chunk_fourcc,
        'vp8': vp8_details, 'mode': pil_mode, 'pil_size': pil_size, 'mtime': mtime_str
    }

print("=" * 80)
print("❌ FAILING IMAGES:")
print("=" * 80)
fail_data = []
for f in FAIL:
    fail_data.append(analyze(f, "FAIL"))

print()
print("=" * 80)
print("✅ WORKING IMAGES:")
print("=" * 80)
ok_data = []
for f in OK:
    ok_data.append(analyze(f, " OK "))

# Summary comparison
print()
print("=" * 80)
print("COMPARISON SUMMARY:")
print("=" * 80)
fail_sizes = [d['size'] for d in fail_data]
ok_sizes = [d['size'] for d in ok_data]
fail_chunks = set(d['chunk'] for d in fail_data)
ok_chunks = set(d['chunk'] for d in ok_data)
fail_modes = set(d['mode'] for d in fail_data)
ok_modes = set(d['mode'] for d in ok_data)

print(f"  FAIL sizes: min={min(fail_sizes)} max={max(fail_sizes)} avg={sum(fail_sizes)//len(fail_sizes)}")
print(f"  OK   sizes: min={min(ok_sizes)} max={max(ok_sizes)} avg={sum(ok_sizes)//len(ok_sizes)}")
print(f"  FAIL chunks: {fail_chunks}")
print(f"  OK   chunks: {ok_chunks}")
print(f"  FAIL pillow modes: {fail_modes}")
print(f"  OK   pillow modes: {ok_modes}")

# Check if any RIFF mismatch
fail_mismatches = sum(1 for d in fail_data if d['size'] != d['riff'])
ok_mismatches = sum(1 for d in ok_data if d['size'] != d['riff'])
print(f"  FAIL RIFF mismatches: {fail_mismatches}")
print(f"  OK   RIFF mismatches: {ok_mismatches}")
