import asyncio, json
from app.db.database import get_pool
from app.core.config import get_settings
from httpx import AsyncClient
import httpx

async def run():
    print('running directly')
