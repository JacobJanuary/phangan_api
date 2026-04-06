"""
Test rendering of ALL today's event images in a real browser context.
Creates an HTML page that loads every image and reports which ones fail via JS onError.
Deploy this to the server and open it in Telegram WebApp browser.
"""
import asyncio
import asyncpg

MEDIA_BASE = "https://api.fastpump.fun/api/media"

async def main():
    conn = await asyncpg.connect(user='thai_app_user', password='ILoveThai@%37', database='ThaiApp', host='127.0.0.1')
    rows = await conn.fetch("""
        SELECT title::text, image_path 
        FROM events 
        WHERE event_date = CURRENT_DATE AND image_path IS NOT NULL 
        ORDER BY event_time;
    """)
    await conn.close()

    html_parts = ["""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<title>Image Audit</title>
<style>
body { background: #111; color: #fff; font-family: sans-serif; padding: 10px; }
.card { display: flex; align-items: center; margin: 4px 0; padding: 6px; border-radius: 8px; }
.card img { width: 60px; height: 60px; object-fit: cover; border-radius: 6px; margin-right: 10px; flex-shrink: 0; }
.ok { background: rgba(0,255,0,0.1); }
.fail { background: rgba(255,0,0,0.3); }
.title { font-size: 12px; }
.url { font-size: 9px; color: #888; word-break: break-all; }
#summary { position: sticky; top: 0; background: #222; padding: 10px; z-index: 10; font-weight: bold; }
</style></head><body>
<div id="summary">Loading...</div>
<div id="grid">
"""]

    for i, row in enumerate(rows):
        title = (row['title'] or '?').replace('"', '&quot;').replace('<', '&lt;')[:60]
        url = f"{MEDIA_BASE}/{row['image_path']}"
        html_parts.append(f"""
<div class="card" id="card-{i}">
  <img src="{url}" 
       onload="markOk({i})" 
       onerror="markFail({i}, '{row['image_path']}')" />
  <div>
    <div class="title">{title}</div>
    <div class="url">{row['image_path']}</div>
  </div>
</div>""")

    total = len(rows)
    html_parts.append(f"""
</div>
<script>
let ok = 0, fail = 0, total = {total};
const fails = [];
function update() {{
  document.getElementById('summary').textContent = 
    `OK: ${{ok}} | FAIL: ${{fail}} | Total: ${{total}} | Remaining: ${{total - ok - fail}}`;
  if (ok + fail === total && fails.length > 0) {{
    document.getElementById('summary').innerHTML += 
      '<br>FAILED FILES:<br>' + fails.map(f => '<span style="color:red;font-size:11px">' + f + '</span>').join('<br>');
  }}
}}
function markOk(i) {{ ok++; document.getElementById('card-'+i).classList.add('ok'); update(); }}
function markFail(i, path) {{ fail++; fails.push(path); document.getElementById('card-'+i).classList.add('fail'); update(); }}
update();
</script></body></html>""")

    html = "\n".join(html_parts)
    with open("/home/ubuntu/Phangan/viberadar-app/dist/image_audit.html", "w") as f:
        f.write(html)
    print(f"Generated audit page with {total} images at /dist/image_audit.html")

asyncio.run(main())
