import asyncio
import httpx
from colorama import Fore, Style, init

init(autoreset=True)

async def check_telegram_avatars():
    from app.core.config import get_settings
    from app.db.database import get_pool

    settings = get_settings()
    if not settings.BOT_TOKEN:
        print(Fore.RED + "BOT_TOKEN missing in config.")
        return

    import asyncpg
    pool = await asyncpg.create_pool(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=settings.DB_PORT
    )
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT id, telegram_id, first_name, avatar_path FROM users WHERE is_phantom = false ORDER BY id"
        )

    print(f"Checking {len(users)} real users via Telegram API...")

    stats = {"success": 0, "no_photo": 0, "api_error": 0, "already_had_path": 0}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for u in users:
            uid = u["telegram_id"]
            if not uid:
                continue

            if u["avatar_path"]:
                stats["already_had_path"] += 1

            # 1. Get User Profile Photos
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getUserProfilePhotos"
            try:
                r = await client.post(url, json={"user_id": uid, "limit": 1})
                if r.status_code != 200:
                    print(Fore.RED + f"❌ {u['first_name']} ({uid}): API Error {r.status_code} - {r.text}")
                    stats["api_error"] += 1
                    continue

                data = r.json()
                if not data.get("ok"):
                    print(Fore.RED + f"❌ {u['first_name']} ({uid}): Telegram Error: {data}")
                    stats["api_error"] += 1
                    continue

                total_count = data["result"]["total_count"]
                if total_count == 0:
                    print(Fore.YELLOW + f"⚠️ {u['first_name']} ({uid}): No photos (Privacy settings or no avatar)")
                    stats["no_photo"] += 1
                    continue

                # 2. Get file_id of the largest resolution of the latest photo
                photos = data["result"]["photos"][0]
                largest_photo = max(photos, key=lambda x: x["width"] * x["height"])
                file_id = largest_photo["file_id"]

                # 3. Get file path
                file_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getFile"
                f_req = await client.post(file_url, json={"file_id": file_id})
                f_data = f_req.json()

                if not f_data.get("ok"):
                    print(Fore.RED + f"❌ {u['first_name']} ({uid}): Could not get file path")
                    stats["api_error"] += 1
                    continue

                file_path = f_data["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_path}"

                # 4. Try downloading header to see if it's accessible
                img_head = await client.head(download_url)
                if img_head.status_code == 200:
                    size = img_head.headers.get("Content-Length", "unknown")
                    print(Fore.GREEN + f"✅ {u['first_name']} ({uid}): Photo explicitly accessible! Size: {size} bytes")
                    stats["success"] += 1
                else:
                    print(Fore.RED + f"❌ {u['first_name']} ({uid}): Download URL failed ({img_head.status_code})")
                    stats["api_error"] += 1

            except Exception as e:
                print(Fore.RED + f"❌ {u['first_name']} ({uid}): Exception - {str(e)}")
                stats["api_error"] += 1

            # Sleep slightly to avoid rate limits
            await asyncio.sleep(0.3)

    print("\n--- 📊 Final Report ---")
    print(Fore.GREEN + f"Successfully accessible via Telegram API: {stats['success']}")
    print(Fore.YELLOW + f"No photo returned (Privacy / None): {stats['no_photo']}")
    print(Fore.RED + f"API Errors / Blocks: {stats['api_error']}")
    print(Style.DIM + f"Users who ALREADY had an avatar_path in DB: {stats['already_had_path']}")

if __name__ == "__main__":
    asyncio.run(check_telegram_avatars())
