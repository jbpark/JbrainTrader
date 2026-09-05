import sys
import os
import requests
import json

# API 테스트
ticker = "005930"
interval = "5분"

url = f"http://localhost:5000/collector/dates/{ticker}?interval={interval}"
print(f"Testing API: {url}")

try:
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
