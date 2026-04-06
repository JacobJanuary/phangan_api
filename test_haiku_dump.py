import asyncio
from anthropic import AsyncAnthropic
from app.core.config import get_settings

async def test():
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    SYSTEM_PROMPT = "You are Vibe Pilot."
    prompt = "Test payload for Vibe Pilot. Reply with {}."
    
    print('Sending payload to claude-haiku-4-5-20251001...')
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        print('Content:', response.content[0].text)
    except Exception as e:
        print('ERROR:', e)

asyncio.run(test())
