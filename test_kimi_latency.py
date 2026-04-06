import asyncio
import time
from anthropic import AsyncAnthropic
from app.core.config import get_settings

async def main():
    settings = get_settings()
    client = AsyncAnthropic(
        api_key=settings.KIMI_CODE_API_KEY,
        base_url='https://api.kimi.com/coding/',
        default_headers={'User-Agent': 'ClaudeCode/1.0'}
    )
    
    prompt = 'Return a generic json with a list of 1-10 string numbers.'
    
    t0 = time.time()
    resp = await client.messages.create(
        model='kimi-for-coding',
        max_tokens=2048,
        messages=[{'role': 'user', 'content': prompt}]
    )
    t1 = time.time()
    print(f'Time: {t1-t0:.2f}s | Output: {resp.content[0].text[:50]}...')

asyncio.run(main())
