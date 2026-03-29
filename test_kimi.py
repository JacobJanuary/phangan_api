import requests
import json

api_key = "sk-kimi-L8LbZ5q9MDPyRTTQopIOwEYgGcQhNWlxvPX3FhLXQsaeK4qaBtIUNKcEiFCQhRtj"

# Test Anthropic compatible endpoint
anthropic_url = "https://api.kimi.com/coding/messages"
# Trying /coding/ as per docs: ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
# According to anthropic sdk, base_url + "/messages" is called.
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
    "User-Agent": "ClaudeCode/1.0"
}
data = {
    "model": "claude-3-opus-20240229", # Often Anthropic endpoints require standard names or ignore them
    "max_tokens": 1024,
    "messages": [
        {"role": "user", "content": "Hello, are you Kimi?"}
    ]
}

print("Testing Anthropic endpoint (https://api.kimi.com/coding/messages)...")
try:
    r = requests.post(anthropic_url, headers=headers, json=data)
    print("Status:", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except:
        print("Text response:", r.text)
except Exception as e:
    print("Error:", e)

# Test Anthropic compatible endpoint with /v1/messages
anthropic_url2 = "https://api.kimi.com/coding/v1/messages"
print("\nTesting Anthropic endpoint (https://api.kimi.com/coding/v1/messages)...")
try:
    r = requests.post(anthropic_url2, headers=headers, json=data)
    print("Status:", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except:
        print("Text response:", r.text)
except Exception as e:
    print("Error:", e)

# Test OpenAI compatible endpoint
openai_url = "https://api.kimi.com/coding/v1/chat/completions"
headers_openai = {
    "Authorization": f"Bearer {api_key}",
    "content-type": "application/json",
}
data_openai = {
    "model": "kimi-for-coding",
    "messages": [
        {"role": "user", "content": "Hello, are you Kimi?"}
    ]
}

print("\nTesting OpenAI endpoint...")
try:
    r = requests.post(openai_url, headers=headers_openai, json=data_openai)
    print("Status:", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except:
        print("Text response:", r.text)
except Exception as e:
    print("Error:", e)
