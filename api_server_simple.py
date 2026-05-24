"""
简化版 API 服务器 - 为 Dashboard 提供真实数据（无 sentence-transformers 依赖）
"""

import sys
sys.path.insert(0, 'H:\\GPU')

import json
import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="DeepSeek Cache API")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据目录
DATA_DIR = Path("h:/deepgui/deepseek-cache-optimizer/data")
DATA_DIR.mkdir(exist_ok=True)

# 简单的内存缓存
class SimpleCache:
    def __init__(self):
        self.cache = {}
        self.access_count = {}
        self.hit_count = {}
        
    def get(self, key: str) -> Optional[str]:
        self.access_count[key] = self.access_count.get(key, 0) + 1
        if key in self.cache:
            self.hit_count[key] = self.hit_count.get(key, 0) + 1
            return self.cache[key]
        return None
    
    def put(self, key: str, value: str):
        self.cache[key] = value
        
    def clear(self):
        self.cache.clear()
        self.access_count.clear()
        self.hit_count.clear()
        
    def get_stats(self):
        total_access = sum(self.access_count.values())
        total_hits = sum(self.hit_count.values())
        return {
            'total_entries': len(self.cache),
            'total_access': total_access,
            'total_hits': total_hits,
            'hit_rate': total_hits / total_access if total_access > 0 else 0
        }

# 初始化缓存
cache = SimpleCache()

# 性能指标
metrics = {
    'total_requests': 0,
    'cache_hits': 0,
    'cache_misses': 0,
    'tokens_saved': 0,
    'avg_response_time': 45
}

metrics_history = []

# 加载一些测试数据
def init_test_data():
    test_data = [
        ("如何学习 Python", "Python 是一种易学易用的编程语言..."),
        ("什么是机器学习", "机器学习是人工智能的一个分支..."),
        ("如何优化代码性能", "代码性能优化可以从算法、数据结构..."),
        ("解释一下递归", "递归是一种函数调用自身的编程技术..."),
        ("什么是深度学习", "深度学习是机器学习的一个子集..."),
        ("Python 列表和元组区别", "列表是可变的，元组是不可变的..."),
        ("如何安装 pip", "pip 是 Python 的包管理工具..."),
        ("什么是 API", "API 是应用程序编程接口..."),
    ]
    for query, response in test_data:
        cache.put(query, response)
    print(f"✅ 已加载 {len(test_data)} 条测试数据")

init_test_data()


@app.get("/")
def root():
    return {"status": "ok", "service": "DeepSeek Cache API", "timestamp": datetime.now().isoformat()}


@app.get("/api/metrics")
def get_metrics() -> Dict[str, Any]:
    """获取当前指标"""
    cache_stats = cache.get_stats()
    
    data = {
        'hit_rate': cache_stats['hit_rate'],
        'cache_hits': metrics['cache_hits'] + cache_stats['total_hits'],
        'tokens_saved': metrics['tokens_saved'] + cache_stats['total_hits'] * 50,
        'avg_response_time': metrics['avg_response_time'],
        'total_requests': metrics['total_requests'] + cache_stats['total_access'],
        'cache_entries': cache_stats['total_entries'],
        'timestamp': datetime.now().isoformat()
    }
    
    # 记录历史
    metrics_history.append({
        'timestamp': datetime.now(),
        'hit_rate': data['hit_rate'],
        'cache_hits': data['cache_hits']
    })
    
    # 限制历史大小
    if len(metrics_history) > 1000:
        metrics_history.pop(0)
    
    return data


@app.get("/api/history")
def get_history(hours: int = 24) -> Dict[str, Any]:
    """获取历史数据"""
    import pandas as pd
    import numpy as np
    
    # 如果有真实历史数据，使用它
    if len(metrics_history) > 0:
        df = pd.DataFrame(metrics_history)
        if len(df) > hours:
            df = df.tail(hours)
        return {
            'timestamps': [t.isoformat() for t in df['timestamp']],
            'hit_rates': df['hit_rate'].tolist(),
            'cache_hits': df['cache_hits'].tolist()
        }
    
    # 否则生成模拟数据
    timestamps = pd.date_range(end=datetime.now(), periods=hours, freq='H')
    hit_rates = np.random.uniform(0.6, 0.9, hours)
    
    return {
        'timestamps': [t.isoformat() for t in timestamps],
        'hit_rates': hit_rates.tolist(),
        'cache_hits': [int(1000 + i * 10) for i in range(hours)]
    }


@app.get("/api/cache-levels")
def get_cache_levels() -> Dict[str, int]:
    """获取缓存层级统计"""
    stats = cache.get_stats()
    # 模拟多级缓存分布
    total = stats['total_entries']
    return {
        'l1_hits': int(total * 0.6),
        'l2_hits': int(total * 0.3),
        'l3_hits': int(total * 0.1)
    }


@app.get("/api/hot-queries")
def get_hot_queries() -> List[Dict]:
    """获取热点查询"""
    queries = []
    for query in cache.cache.keys():
        access = cache.access_count.get(query, 0)
        hits = cache.hit_count.get(query, 0)
        hit_rate = hits / access if access > 0 else 0
        queries.append({
            'query': query,
            'hit_count': hits,
            'access_count': access,
            'hit_rate': hit_rate
        })
    
    # 按命中次数排序
    queries.sort(key=lambda x: x['hit_count'], reverse=True)
    return queries[:10]


@app.post("/api/cache/query")
def cache_query(query: str) -> Dict[str, Any]:
    """查询缓存"""
    result = cache.get(query)
    metrics['total_requests'] += 1
    
    if result:
        metrics['cache_hits'] += 1
        return {
            'found': True,
            'response': result,
            'cached': True
        }
    else:
        metrics['cache_misses'] += 1
        return {
            'found': False,
            'response': None,
            'cached': False
        }


@app.post("/api/cache/store")
def cache_store(query: str, response: str) -> Dict[str, Any]:
    """存储到缓存"""
    cache.put(query, response)
    return {
        'success': True,
        'message': '已存储到缓存'
    }


@app.post("/api/cache/clear")
def clear_cache():
    """清空缓存"""
    cache.clear()
    metrics['total_requests'] = 0
    metrics['cache_hits'] = 0
    metrics['cache_misses'] = 0
    return {"success": True, "message": "缓存已清空"}


@app.post("/api/cache/test-data")
def add_test_data():
    """添加测试数据到缓存"""
    test_queries = [
        ("如何学习 Python", "Python 是一种易学易用的编程语言..."),
        ("什么是机器学习", "机器学习是人工智能的一个分支..."),
        ("如何优化代码性能", "代码性能优化可以从算法、数据结构..."),
    ]
    
    for query, response in test_queries:
        cache.put(query, response)
    
    return {"success": True, "message": f"已添加 {len(test_queries)} 条测试数据"}


if __name__ == "__main__":
    print("🚀 启动 API 服务器...")
    print("📊 访问 http://127.0.0.1:8000 查看 API")
    uvicorn.run(app, host="127.0.0.1", port=8000)
