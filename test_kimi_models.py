import requests
import json

api_key = "sk-kimi-L8LbZ5q9MDPyRTTQopIOwEYgGcQhNWlxvPX3FhLXQsaeK4qaBtIUNKcEiFCQhRtj"

anthropic_url = "https://api.kimi.com/coding/v1/models"
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
    "User-Agent": "ClaudeCode/1.0"
}

try:
    r = requests.get(anthropic_url, headers=headers)
    print("Status:", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except:
        print("Text response:", r.text)
except Exception as e:
    print("Error:", e)
