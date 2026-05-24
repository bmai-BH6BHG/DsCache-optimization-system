"""
API 服务器 - 为 Dashboard 提供真实缓存数据
从 MCP 服务器写入的共享 JSON 读取实时统计
"""

import sys
sys.path.insert(0, 'H:\\GPU')

import os
import json
import sqlite3
import time
from datetime import datetime
from typing import Dict, Any, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'cache_l2.db')
METRICS_DB_PATH = os.path.join(DATA_DIR, 'metrics.db')
STATS_JSON = os.path.join(DATA_DIR, 'cache_stats.json')
L3_PATH = os.path.join(DATA_DIR, 'cache_l3')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(L3_PATH, exist_ok=True)

app = FastAPI(title="DeepSeek Cache API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                created_at REAL,
                expires_at REAL,
                hit_count INTEGER DEFAULT 0,
                last_accessed REAL DEFAULT 0,
                size INTEGER DEFAULT 0
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)')
        conn.commit()
        conn.close()
    except Exception:
        pass

    try:
        conn = sqlite3.connect(METRICS_DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                total_requests INTEGER,
                cache_hits INTEGER,
                cache_misses INTEGER,
                hit_rate REAL,
                avg_response_time REAL,
                tokens_saved INTEGER,
                l1_hits INTEGER,
                l2_hits INTEGER,
                l3_hits INTEGER
            )
        ''')
        conn.commit()
        conn.close()
    except Exception:
        pass


_init_db()


def _read_mcp_stats() -> Dict:
    try:
        if os.path.exists(STATS_JSON):
            with open(STATS_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _read_sqlite(query, params=()):
    try:
        if not os.path.exists(DB_PATH):
            return []
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def _read_metrics_history(hours=24):
    try:
        hours = int(hours)
    except Exception:
        hours = 24
    try:
        conn = sqlite3.connect(METRICS_DB_PATH)
        c = conn.cursor()
        cutoff = time.time() - hours * 3600
        c.execute(
            "SELECT timestamp, total_requests, cache_hits, cache_misses, hit_rate, "
            "avg_response_time, tokens_saved, l1_hits, l2_hits, l3_hits "
            "FROM metrics_history WHERE timestamp >= ? ORDER BY timestamp ASC",
            (cutoff,)
        )
        rows = c.fetchall()
        conn.close()
        keys = ['timestamp', 'total_requests', 'cache_hits', 'cache_misses',
                'hit_rate', 'avg_response_time', 'tokens_saved', 'l1_hits', 'l2_hits', 'l3_hits']
        return [dict(zip(keys, row)) for row in rows]
    except Exception:
        return []


def _write_metric_snapshot(m):
    try:
        ts = m.get('timestamp', time.time())
        if isinstance(ts, str):
            ts = time.time()
        conn = sqlite3.connect(METRICS_DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO metrics_history "
            "(timestamp, total_requests, cache_hits, cache_misses, hit_rate, "
            "avg_response_time, tokens_saved, l1_hits, l2_hits, l3_hits) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, m.get('total_requests', 0), m.get('cache_hits', 0),
             m.get('cache_misses', 0), m.get('hit_rate', 0),
             m.get('avg_response_time', 0), m.get('tokens_saved', 0),
             m.get('l1_hits', 0), m.get('l2_hits', 0), m.get('l3_hits', 0))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _fmt_ts(t):
    try:
        return datetime.fromtimestamp(float(t)).isoformat()
    except Exception:
        return datetime.now().isoformat()


@app.get("/")
def root():
    return {"status": "ok", "service": "DeepSeek Cache API"}


@app.get("/api/metrics")
def get_metrics():
    mcp = _read_mcp_stats()
    if mcp:
        data = {
            'hit_rate': mcp.get('hit_rate', 0),
            'cache_hits': mcp.get('cache_hits', 0),
            'cache_misses': mcp.get('cache_misses', 0),
            'tokens_saved': mcp.get('tokens_saved', 0),
            'avg_response_time': mcp.get('avg_response_time', 0),
            'total_requests': mcp.get('total_requests', 0),
            'l1_hits': mcp.get('l1_hits', 0),
            'l2_hits': mcp.get('l2_hits', 0),
            'l3_hits': mcp.get('l3_hits', 0),
            'l2_size': mcp.get('l2_size', 0),
            'l3_size': mcp.get('l3_size', 0),
            'timestamp': mcp.get('timestamp', time.time()),
        }
    else:
        l2_rows = _read_sqlite("SELECT COUNT(*) FROM cache")
        l2_size = l2_rows[0][0] if l2_rows else 0
        l3_size = 0
        try:
            for root, dirs, files in os.walk(L3_PATH):
                l3_size += sum(1 for f in files if f.endswith('.cache'))
        except Exception:
            pass
        data = {
            'hit_rate': 0, 'cache_hits': 0, 'cache_misses': 0,
            'tokens_saved': 0, 'avg_response_time': 0,
            'total_requests': 0, 'l1_hits': 0, 'l2_hits': 0,
            'l3_hits': 0, 'l2_size': l2_size, 'l3_size': l3_size,
            'timestamp': time.time(),
        }

    _write_metric_snapshot(data)
    return data


@app.get("/api/history")
def get_history(hours: int = 24):
    history = _read_metrics_history(hours=hours)
    if not history:
        return {'timestamps': [], 'hit_rates': [], 'cache_hits': []}
    return {
        'timestamps': [_fmt_ts(h['timestamp']) for h in history],
        'hit_rates': [h['hit_rate'] for h in history],
        'cache_hits': [h['cache_hits'] for h in history]
    }


@app.get("/api/cache-levels")
def get_cache_levels():
    mcp = _read_mcp_stats()
    if mcp:
        return {
            'l1_hits': mcp.get('l1_hits', 0),
            'l2_hits': mcp.get('l2_hits', 0),
            'l3_hits': mcp.get('l3_hits', 0),
        }
    return {'l1_hits': 0, 'l2_hits': 0, 'l3_hits': 0}


@app.get("/api/hot-queries")
def get_hot_queries():
    mcp = _read_mcp_stats()
    if mcp and mcp.get('hot_queries'):
        total = sum(q['hits'] for q in mcp['hot_queries']) or 1
        return [{'query': q['query'], 'hit_count': q['hits'], 'hit_rate': q['hits'] / total} for q in mcp['hot_queries']]
    
    rows = _read_sqlite(
        "SELECT key, hit_count FROM cache WHERE hit_count > 0 ORDER BY hit_count DESC LIMIT 10"
    )
    if not rows:
        return []
    total = sum(r[1] for r in rows) or 1
    return [{'query': r[0], 'hit_count': r[1], 'hit_rate': r[1] / total} for r in rows]


@app.get("/api/response-time")
def get_response_time():
    """获取响应时间对比数据"""
    mcp = _read_mcp_stats()
    avg_time = 0

    if mcp and mcp.get('avg_response_time'):
        avg_time = mcp['avg_response_time']

    if avg_time <= 0:
        # 从历史记录中获取
        try:
            conn = sqlite3.connect(METRICS_DB_PATH)
            c = conn.cursor()
            c.execute(
                "SELECT AVG(avg_response_time) FROM metrics_history "
                "WHERE avg_response_time > 0 ORDER BY timestamp DESC LIMIT 100"
            )
            row = c.fetchone()
            conn.close()
            if row and row[0]:
                avg_time = row[0]
        except Exception:
            pass

    if avg_time <= 0:
        avg_time = 200

    # 估算缓存命中/未命中的响应时间
    # 缓存命中通常非常快（约为平均的 10-15%）
    # 缓存未命中需要实际调用 API（约为平均的 150-200%）
    cache_hit_time = max(5, avg_time * 0.12)
    cache_miss_time = avg_time * 1.8

    return {
        'cache_hit_time': round(cache_hit_time, 1),
        'cache_miss_time': round(cache_miss_time, 1),
        'avg_time': round(avg_time, 1)
    }


if __name__ == "__main__":
    print(f"API server: http://127.0.0.1:8000")
    print(f"Stats JSON: {STATS_JSON}")
    uvicorn.run(app, host="127.0.0.1", port=8000)
