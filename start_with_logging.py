
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import requests
import fastapi
import uvicorn
sys.path.insert(0, 'H:\\GPU')

# 现在执行 relay_server
print("="*60)
print("Starting DeepSeek Cache Relay Server")
print("="*60)
exec(open("relay_server.py", encoding="utf-8").read())
