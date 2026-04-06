import asyncio
from app.db.database import get_pool
async def test():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE events SET event_time='13:45' WHERE id=3220")
        res = await conn.fetchval("SELECT event_time FROM events WHERE id=3220")
        print('DB TIME NOW:', res)
asyncio.run(test())
