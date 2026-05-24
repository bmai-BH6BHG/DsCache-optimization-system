import sys
import os

# H:\GPU 必须在最前面
sys.path.insert(0, r'H:\GPU')
sys.path.insert(1, r'h:\deepgui\deepseek-cache-optimizer')

os.environ['DEEPSEEK_CACHE_CONFIG'] = './config/default.yaml'
os.environ['DEEPSEEK_CACHE_DATA_DIR'] = './data'

# 预加载所有依赖（防止被其他模块的导入覆盖路径）
import jieba
import numpy
import sklearn
import sentence_transformers

print(f"jieba: {jieba.__file__}", file=sys.stderr)
print(f"numpy: {numpy.__file__}", file=sys.stderr)
print(f"sentence_transformers: {sentence_transformers.__file__}", file=sys.stderr)

import mcp
print(f"mcp: {mcp.__file__}", file=sys.stderr)

from mcp_server.server import DeepSeekCacheServer
import asyncio

async def main():
    server = DeepSeekCacheServer()
    await server.run()

asyncio.run(main())
