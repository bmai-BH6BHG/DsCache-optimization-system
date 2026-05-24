
import requests
import json
import time
import sys

base_url = "http://127.0.0.1:8001"
headers = {
    "Authorization": "Bearer sk-your-key-here", 
    "Content-Type": "application/json"
}

test_query = "你好，请介绍一下你自己"

print("="*60)
print("⚡ 速度测试开始！")
print("="*60)
print(f"测试查询: {test_query}")
print()

# 第一次请求（缓存miss）
print("1️⃣  第一次请求（缓存MISS）...")
payload = {
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": test_query}],
    "max_tokens": 50,
    "stream": False
}
t1 = time.time()
resp1 = requests.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload, timeout=60)
time1 = (time.time() - t1) * 1000
print(f"   状态: {resp1.status_code}")
print(f"   耗时: {time1:.1f} ms")

print()

# 第二次请求（缓存HIT，应该超快！）
print("2️⃣  第二次请求（缓存HIT，应该极速！）...")
t2 = time.time()
resp2 = requests.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload, timeout=60)
time2 = (time.time() - t2) * 1000
print(f"   状态: {resp2.status_code}")
print(f"   耗时: {time2:.1f} ms")

print()
print("="*60)
print(f"🚀 速度提升: {time1/time2:.1f}x 倍！")
print("="*60)

if time2 < 100:
    print("✅ SUCCESS: 缓存命中速度超快！")
else:
    print("⚠️  缓存速度可以进一步优化")
