import asyncio
import os
import time

# Ensure we have the OpenAI SDK installed: pip install openai
from openai import AsyncOpenAI

DEEPSEEK_API_KEY = "sk-26727fc3f68848caa3c00d638298aef3"

async def test_deepseek_reasoner():
    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )
    
    prompt = """
    We have 3 events:
    1. Beach Party (60 mins, distance 5 mins)
    2. Yoga Session (90 mins, distance 15 mins)
    3. Tech Meetup (60 mins, distance 10 mins)
    Plan the best day for a tech enthusiast who likes to chill.
    Reply with strict JSON.
    """
    
    print("Sending prompt to deepseek-reasoner...")
    start_time = time.time()
    
    try:
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": "You are Vibe Pilot, output only JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        # DeepSeek Reasoner includes the thinking process in choices[0].message.reasoning_content (optional extension for logging)
        # But we only need .content
        content = response.choices[0].message.content
        print(f"Time Taken: {time.time() - start_time:.2f}s")
        print("Response:", content[:500], "...")
    except Exception as e:
        print("Error during DeepSeek API call:", e)

if __name__ == "__main__":
    asyncio.run(test_deepseek_reasoner())
