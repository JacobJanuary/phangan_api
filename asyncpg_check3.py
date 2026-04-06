import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(user='thai_app_user', password='ILoveThai@%37', database='ThaiApp', host='127.0.0.1')
        total = await conn.fetchval("SELECT COUNT(*) FROM events;")
        local = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path NOT LIKE 'http%';")
        external = await conn.fetchval("SELECT COUNT(*) FROM events WHERE image_path LIKE 'http%';")
        print(f"Total: {total}, Local WebP: {local}, External HTTP: {external}")
        await conn.close()
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
