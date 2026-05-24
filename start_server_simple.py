
# 这个是简化版启动脚本
import sys
import os

# 保证我们在正确的目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 1. 导入标准依赖
import requests
import fastapi
import uvicorn

# 2. 现在添加 GPU 路径
sys.path.insert(0, 'H:\\GPU')

# 3. 执行 relay_server.py
exec(open("relay_server.py", encoding="utf-8").read())
