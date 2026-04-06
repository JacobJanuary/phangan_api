import asyncio
from openai import AsyncOpenAI
import json
from app.core.config import get_settings

async def test():
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url='https://api.deepseek.com')
    
    SYSTEM_PROMPT = """You are Vibe Pilot, an AI day planner. Return strictly JSON matches format:
    {"plan": []}
    """
    prompt = "Test payload for Vibe Pilot. 1 event: Party 9 PM."
    
    print('Sending payload to deepseek-reasoner...')
    try:
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        print('Content:', response.choices[0].message.content)
        if hasattr(response.choices[0].message, 'reasoning_content'):
            print('Reasoning length:', len(response.choices[0].message.reasoning_content or ''))
    except Exception as e:
        print(e)

asyncio.run(test())
