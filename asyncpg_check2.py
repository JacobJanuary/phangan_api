import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(user='thai_app_user', password='ILoveThai@%37', database='ThaiApp', host='127.0.0.1')
        rows = await conn.fetch("SELECT title, image_path FROM events WHERE title::text NOT LIKE '%Ребефинг%' LIMIT 5;")
        for row in rows:
            print(f"Title: {row['title']}, ImagePath: {row['image_path']}")
        await conn.close()
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
