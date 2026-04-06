import asyncio, httpx
from app.core.security import create_access_token

async def test():
    token = create_access_token({"sub": "1", "role": "admin"})
    async with httpx.AsyncClient() as client:
        r = await client.put('http://127.0.0.1:62537/api/v1/events/3220', 
            json={"event_time": "16:00"},
            headers={"Authorization": f"Bearer {token}"}
        )
        print('HTTP', r.status_code)
        print(r.text)
asyncio.run(test())
