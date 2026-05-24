
import requests
import json
import sys

base_url = "http://127.0.0.1:8001"

print("=" * 60)
print("Testing API endpoints...")
print("=" * 60)

# 1. 先测试 / 仪表板
print("\n1. Testing GET / (dashboard)...")
try:
    r = requests.get(f"{base_url}/")
    print(f"   Status: {r.status_code}")
    print(f"   Response snippet: {r.text[:200]}")
except Exception as e:
    print(f"   ERROR: {e}")

# 2. 测试 /api/metrics
print("\n2. Testing GET /api/metrics...")
try:
    r = requests.get(f"{base_url}/api/metrics")
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text[:300]}")
except Exception as e:
    print(f"   ERROR: {e}")

# 3. 测试 /api/hot-queries
print("\n3. Testing GET /api/hot-queries...")
try:
    r = requests.get(f"{base_url}/api/hot-queries")
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text}")
except Exception as e:
    print(f"   ERROR: {e}")

# 4. 测试 /admin/config
print("\n4. Testing GET /admin/config...")
try:
    r = requests.get(f"{base_url}/admin/config")
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text}")
except Exception as e:
    print(f"   ERROR: {e}")

# 5. 测试 OpenAI 兼容端点 - /v1/models
print("\n5. Testing GET /v1/models (needs SK)...")
try:
    headers = {"Authorization": "Bearer sk-b11d27372dc729ee8840067d31eb51a1ad08d8f85c1b004b"}
    r = requests.get(f"{base_url}/v1/models", headers=headers)
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text}")
except Exception as e:
    print(f"   ERROR: {e}")

# 6. 测试实际的 /v1/chat/completions
print("\n6. Testing POST /v1/chat/completions...")
try:
    headers = {
        "Authorization": "Bearer sk-b11d27372dc729ee8840067d31eb51a1ad08d8f85c1b004b", 
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": "测试一下"}],
        "max_tokens": 10,
        "stream": False
    }
    print(f"   Payload: {json.dumps(payload, ensure_ascii=False)}")
    r = requests.post(
        f"{base_url}/v1/chat/completions", 
        headers=headers, 
        json=payload, 
        timeout=30
    )
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.text}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    print(traceback.format_exc())

print("\n" + "=" * 60)
