
"""DeepSeek Cache Optimizer - 轻量版单文件服务"""
import sys
import os
import json
import time
import hashlib
import re
import secrets
import sqlite3
from datetime import datetime

import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn

# 导入记忆系统
from memory_system import MemorySystem


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATS_JSON = os.path.join(DATA_DIR, 'cache_stats.json')
CONFIG_JSON = os.path.join(DATA_DIR, 'config.json')
METRICS_DB = os.path.join(DATA_DIR, 'metrics.db')
CACHE_DB = os.path.join(DATA_DIR, 'response_cache.db')
os.makedirs(DATA_DIR, exist_ok=True)

# 初始化记忆系统
memory_system = MemorySystem(DATA_DIR)


app = FastAPI(title="DeepSeek Cache Optimizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
security_scheme = HTTPBearer(auto_error=False)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQ] {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    auth = request.headers.get("Authorization", "none")[:30] if request.headers.get("Authorization") else "none"
    print(f"[REQ] Auth: {auth}")
    response = await call_next(request)
    print(f"[REQ] {request.method} {request.url.path} -> {response.status_code}")
    return response


# 全局状态
metrics = {
    'total_requests': 0, 'cache_hits': 0, 'cache_misses': 0,
    'tokens_saved': 0, 'avg_response_time': 0,
    'total_api_time': 0, 'total_cache_time': 0,
}
request_type_counts = {}
query_history = []
fast_hash_cache = {}
fast_query_text = {}
fast_cache_ttl = {}


def _load_config():
    try:
        if os.path.exists(CONFIG_JSON):
            with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    sk = "sk-" + secrets.token_hex(24)
    cfg = {
        "sk": sk,
        "upstream_url": "https://api.deepseek.com",
        "upstream_key": "",
        "upstream_model": "deepseek-v4-flash",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "port": 8001,
    }
    _save_config(cfg)
    return cfg


def _save_config(cfg):
    with open(CONFIG_JSON, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


config = _load_config()
print("\n" + "="*60)
print("  SK 密钥:  " + config["sk"])
print("  上游 API:  " + config["upstream_url"])
print("  模型:      " + config["upstream_model"])
print("="*60 + "\n")


def init_metrics_db():
    try:
        c = sqlite3.connect(METRICS_DB)
        c.execute('''CREATE TABLE IF NOT EXISTS metrics_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL,
            total_requests INTEGER, cache_hits INTEGER, cache_misses INTEGER,
            hit_rate REAL, avg_response_time REAL, tokens_saved INTEGER,
            l1_hits INTEGER, l2_hits INTEGER, l3_hits INTEGER)''')
        c.commit()
        c.close()
    except Exception:
        pass


def init_cache_db():
    c = sqlite3.connect(CACHE_DB)
    c.execute('''CREATE TABLE IF NOT EXISTS response_cache(
        cache_key TEXT PRIMARY KEY, query_text TEXT, response_text TEXT,
        created_at REAL, hit_count INTEGER DEFAULT 1)''')
    c.commit()
    c.close()


def load_persisted_cache():
    try:
        c = sqlite3.connect(CACHE_DB)
        rows = c.execute("SELECT cache_key, query_text, response_text, created_at FROM response_cache").fetchall()
        c.close()
        for row in rows:
            key, query_text, response_text, created_at = row
            fast_hash_cache[key] = response_text
            fast_query_text[key] = query_text
            fast_cache_ttl[key] = created_at
        print("[CACHE] Loaded " + str(len(rows)) + " persisted cache entries")
    except Exception as e:
        print("[CACHE] Load error: " + str(e))


def save_to_db(cache_key, query_text, response_text, timestamp):
    try:
        c = sqlite3.connect(CACHE_DB)
        c.execute("INSERT OR REPLACE INTO response_cache VALUES(?,?,?,?,COALESCE((SELECT hit_count FROM response_cache WHERE cache_key=?),0)+1)",
                  (cache_key, query_text, response_text, timestamp, cache_key))
        c.commit()
        c.close()
    except Exception:
        pass


init_metrics_db()
init_cache_db()
load_persisted_cache()


async def verify_sk(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    if credentials and credentials.credentials == config["sk"]:
        return True
    # 调试模式：允许无认证通过，打印日志
    if not credentials:
        print("[AUTH] No credentials provided, allowing (debug mode)")
        return True
    print(f"[AUTH] Wrong SK: {credentials.credentials[:20]}..., expected: {config['sk'][:20]}...")
    raise HTTPException(status_code=401, detail="Invalid SK key")


def detect_request_type(query):
    q = query.lower()
    if re.search(r'```|def |function |class |import |写|编写|生成|create|write|generate|implement|代码|code|函数', q):
        return 'code_generation'
    if any(k in q for k in ['bug', 'error', 'debug', 'fix', '报错', '错误', '调试']):
        return 'debugging'
    if any(k in q for k in ['什么是', '解释', 'explain', 'what is', '含义', '区别']):
        return 'code_explanation'
    if any(k in q for k in ['你好', '您好', '谢谢', 'help', 'hi', 'hello']):
        return 'conversation'
    return 'general_qa'


def simple_normalize(text):
    text = text.lower().strip()
    for p in "，。！？、；：""''（）【】《》,.:;!?\"'()[]{}":
        text = text.replace(p, " ")
    return " ".join(text.split())


def jaccard_similarity(s1, s2):
    s1_grams = set(s1[i:i+2] for i in range(len(s1)-1))
    s2_grams = set(s2[i:i+2] for i in range(len(s2)-1))
    if not s1_grams or not s2_grams:
        return 0.0
    inter = len(s1_grams & s2_grams)
    union = len(s1_grams | s2_grams)
    if union > 0:
        return inter / union
    else:
        return 0.0


def dump_stats():
    try:
        total = metrics['total_requests']
        if total > 0:
            hr = metrics['cache_hits'] / total
        else:
            hr = 0

        hot_list = []
        try:
            c = sqlite3.connect(CACHE_DB)
            rows = c.execute("SELECT query_text, hit_count FROM response_cache ORDER BY hit_count DESC LIMIT 5").fetchall()
            c.close()
            for r in rows:
                hot_list.append({'query': r[0][:60] if r[0] else '', 'hits': r[1]})
        except Exception:
            pass

        stats = {
            'timestamp': time.time(), 'hit_rate': hr,
            'cache_hits': metrics['cache_hits'], 'cache_misses': metrics['cache_misses'],
            'total_requests': total, 'tokens_saved': metrics['tokens_saved'],
            'avg_response_time': metrics['avg_response_time'],
            'cache_hit_time': max(metrics['total_cache_time'] / max(metrics['cache_hits'], 1), 5),
            'cache_miss_time': max(metrics['total_api_time'] / max(metrics['cache_misses'], 1), 200),
            'l1_hits': 0, 'l2_hits': 0, 'l3_hits': 0,
            'l2_size': len(fast_hash_cache), 'l3_size': len(fast_hash_cache),
            'semantic_cache_size': len(fast_hash_cache),
            'hot_queries': hot_list,
            'code_generation': request_type_counts.get('code_generation', 0),
            'code_explanation': request_type_counts.get('code_explanation', 0),
            'debugging': request_type_counts.get('debugging', 0),
            'conversation': request_type_counts.get('conversation', 0),
            'general_qa': request_type_counts.get('general_qa', 0),
        }
        with open(STATS_JSON, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False)

        try:
            c = sqlite3.connect(METRICS_DB)
            c.execute("INSERT INTO metrics_history VALUES(NULL,?,?,?,?,?,?,?,?,?)", (
                stats['timestamp'], stats['total_requests'], stats['cache_hits'],
                stats['cache_misses'], stats['hit_rate'], stats['avg_response_time'],
                stats['tokens_saved'], stats['l1_hits'], stats['l2_hits'], stats['l3_hits']))
            c.commit()
            c.close()
        except Exception:
            pass
    except Exception:
        pass


@app.get("/")
def dashboard():
    path = os.path.join(BASE_DIR, 'dashboard.html')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("dashboard.html not found")


@app.get("/v1/models")
async def list_models(_: bool = Depends(verify_sk)):
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "created": int(time.time()), "owned_by": "deepseek"} for m in config.get("models", ["deepseek-v4-flash"])]
    }

# 兼容端点：有些客户端用 /models 而不是 /v1/models
@app.get("/models")
async def list_models_compat(_: bool = Depends(verify_sk)):
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "created": int(time.time()), "owned_by": "deepseek"} for m in config.get("models", ["deepseek-v4-flash"])]
    }

# 兼容端点：/chat/completions
@app.post("/chat/completions")
async def chat_completions_compat(request: Request, _: bool = Depends(verify_sk)):
    return await chat_completions(request, _)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, _: bool = Depends(verify_sk)):
    global metrics
    try:
        body = await request.json()
        messages = body.get('messages', [])

        user_content = ''
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, str):
                    user_content = content
                else:
                    user_content = json.dumps(content, ensure_ascii=False)
                break
        if not user_content:
            user_content = json.dumps(messages, ensure_ascii=False)

        t0 = time.time()
        metrics['total_requests'] += 1
        rt = detect_request_type(user_content)
        request_type_counts[rt] = request_type_counts.get(rt, 0) + 1

        cache_key = hashlib.md5(user_content.lower().strip().encode()).hexdigest()
        current_time = time.time()

        # 1. 精确哈希匹配
        if cache_key in fast_hash_cache:
            if current_time - fast_cache_ttl.get(cache_key, 0) < 86400 * 7:
                response_text = fast_hash_cache[cache_key]
                metrics['cache_hits'] += 1
                cache_time = (time.time() - t0) * 1000
                metrics['total_cache_time'] += cache_time
                metrics['tokens_saved'] += len(response_text) // 4
                metrics['avg_response_time'] = round(
                    (metrics['avg_response_time'] * (metrics['total_requests'] - 1) + cache_time) / metrics['total_requests'], 2)
                query_history.append({'query': user_content, 'type': rt, 'from_cache': True,
                                      'similarity': 1.0, 'time_ms': cache_time, 'timestamp': current_time})
                save_to_db(cache_key, user_content, response_text, fast_cache_ttl[cache_key])
                
                try:
                    memory_system.add_memory(
                        content=f"Q: {user_content}\nA: {response_text}",
                        memory_type='episodic',
                        metadata={'request_type': rt, 'cache_hit': True},
                        importance=0.7
                    )
                except Exception:
                    pass
                
                dump_stats()
                
                is_stream = body.get('stream', False)
                if is_stream:
                    from fastapi.responses import StreamingResponse
                    import asyncio
                    
                    def cached_stream():
                        chunk_id = "cache-" + str(int(current_time))
                        created = int(current_time)
                        model = config["upstream_model"]
                        for i, char in enumerate(response_text):
                            chunk = {
                                "id": chunk_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": char} if i < len(response_text) - 1 else {"content": char},
                                    "finish_reason": None if i < len(response_text) - 1 else "stop"
                                }]
                            }
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                    
                    return StreamingResponse(cached_stream(), media_type="text/event-stream")
                
                return {
                    "id": "cache-" + str(int(current_time)), "object": "chat.completion", "created": int(current_time),
                    "model": config["upstream_model"],
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": len(user_content)//4, "completion_tokens": len(response_text)//4,
                               "total_tokens": (len(user_content)+len(response_text))//4, "cached": True}
                }
            else:
                del fast_hash_cache[cache_key]
                del fast_cache_ttl[cache_key]
                if cache_key in fast_query_text:
                    del fast_query_text[cache_key]

        # 2. 搜索记忆系统获取相关上下文
        relevant_memories = []
        try:
            relevant_memories = memory_system.search_memories(user_content, limit=3)
        except Exception:
            pass
        
        # 3. 搜索知识库获取相关知识
        relevant_knowledge = []
        try:
            relevant_knowledge = memory_system.search_knowledge(user_content, limit=2)
        except Exception:
            pass

        # 4. 轻量相似度匹配
        normalized_query = simple_normalize(user_content)
        best_match_key = None
        best_similarity = 0.0
        for cached_key, cached_query in fast_query_text.items():
            normalized_cached = simple_normalize(cached_query)
            sim = jaccard_similarity(normalized_query, normalized_cached)
            if sim > best_similarity and sim > 0.55:
                best_similarity = sim
                best_match_key = cached_key

        if best_match_key and best_match_key in fast_hash_cache:
            response_text = fast_hash_cache[best_match_key]
            metrics['cache_hits'] += 1
            cache_time = (time.time() - t0) * 1000
            metrics['total_cache_time'] += cache_time
            metrics['tokens_saved'] += len(response_text) // 4
            metrics['avg_response_time'] = round(
                (metrics['avg_response_time'] * (metrics['total_requests'] - 1) + cache_time) / metrics['total_requests'], 2)
            query_history.append({'query': user_content, 'type': rt, 'from_cache': True,
                                  'similarity': best_similarity, 'time_ms': cache_time, 'timestamp': current_time})
            save_to_db(cache_key, user_content, response_text, current_time)
            fast_hash_cache[cache_key] = response_text
            fast_query_text[cache_key] = user_content
            fast_cache_ttl[cache_key] = current_time
            dump_stats()
            
            is_stream = body.get('stream', False)
            if is_stream:
                from fastapi.responses import StreamingResponse
                
                def semantic_cached_stream():
                    chunk_id = "cache-" + str(int(current_time))
                    created = int(current_time)
                    model = config["upstream_model"]
                    for i, char in enumerate(response_text):
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": char},
                                "finish_reason": None if i < len(response_text) - 1 else "stop"
                            }]
                        }
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(semantic_cached_stream(), media_type="text/event-stream")
            
            return {
                "id": "cache-" + str(int(current_time)), "object": "chat.completion", "created": int(current_time),
                "model": config["upstream_model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(user_content)//4, "completion_tokens": len(response_text)//4,
                           "total_tokens": (len(user_content)+len(response_text))//4, "cached": True}
            }

        # 3. 未命中，转发上游
        metrics['cache_misses'] += 1
        if not config.get('upstream_key'):
            dump_stats()
            return JSONResponse({"error": "上游 API Key 未配置，请在前端面板设置"}, status_code=502)

        try:
            headers = {"Authorization": "Bearer " + config["upstream_key"], "Content-Type": "application/json"}
            api_body = body.copy()
            if 'model' not in api_body or not api_body['model']:
                api_body['model'] = config['upstream_model']

            is_stream = api_body.get('stream', False)
            api_t0 = time.time()

            if is_stream:
                resp = requests.post(config['upstream_url'] + "/v1/chat/completions",
                                   headers=headers, json=api_body, timeout=300, stream=True)
                api_time = (time.time() - api_t0) * 1000

                if resp.status_code == 200:
                    from fastapi.responses import StreamingResponse
                    full_response_text = [""]

                    def generate():
                        for chunk in resp.iter_content(chunk_size=None):
                            if chunk:
                                yield chunk
                                try:
                                    chunk_str = chunk.decode('utf-8', errors='ignore')
                                    if chunk_str.startswith('data:'):
                                        chunk_data = chunk_str[5:].strip()
                                        if chunk_data and chunk_data != '[DONE]':
                                            try:
                                                chunk_json = json.loads(chunk_data)
                                                if 'choices' in chunk_json and len(chunk_json['choices']) > 0:
                                                    delta = chunk_json['choices'][0].get('delta', {})
                                                    if 'content' in delta:
                                                        full_response_text[0] += delta['content']
                                            except Exception:
                                                pass
                                except Exception:
                                    pass

                    def finalize():
                        try:
                            text = full_response_text[0] if full_response_text else ""
                            if text:
                                fast_hash_cache[cache_key] = text
                                fast_query_text[cache_key] = user_content
                                fast_cache_ttl[cache_key] = current_time
                                save_to_db(cache_key, user_content, text, current_time)
                                metrics['total_api_time'] += api_time
                                metrics['avg_response_time'] = round(
                                    (metrics['avg_response_time'] * (metrics['total_requests'] - 1) + api_time) / metrics['total_requests'], 2)
                                query_history.append({'query': user_content, 'type': rt, 'from_cache': False,
                                                      'time_ms': api_time, 'timestamp': current_time})
                                dump_stats()
                        except Exception:
                            pass

                    metrics['total_api_time'] += api_time
                    metrics['avg_response_time'] = round(
                        (metrics['avg_response_time'] * (metrics['total_requests'] - 1) + api_time) / metrics['total_requests'], 2)
                    query_history.append({'query': user_content, 'type': rt, 'from_cache': False,
                                          'time_ms': api_time, 'timestamp': current_time})
                    dump_stats()
                    response = StreamingResponse(generate(), media_type="text/event-stream")
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        loop.call_later(1, finalize)
                    except Exception:
                        pass
                    return response
                else:
                    dump_stats()
                    try:
                        err = resp.json()
                    except Exception:
                        err = {"error": resp.text}
                    return JSONResponse({"error": "Upstream error (" + str(resp.status_code) + ")", "detail": err}, status_code=502)
            else:
                resp = requests.post(config['upstream_url'] + "/v1/chat/completions",
                                   headers=headers, json=api_body, timeout=300)
                api_time = (time.time() - api_t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    response_text = ""
                    if 'choices' in data and len(data['choices']) > 0:
                        choice = data['choices'][0]
                        if 'message' in choice and 'content' in choice['message']:
                            response_text = choice['message']['content']

                    metrics['total_api_time'] += api_time
                    metrics['avg_response_time'] = round(
                        (metrics['avg_response_time'] * (metrics['total_requests'] - 1) + api_time) / metrics['total_requests'], 2)
                    fast_hash_cache[cache_key] = response_text
                    fast_query_text[cache_key] = user_content
                    fast_cache_ttl[cache_key] = current_time
                    save_to_db(cache_key, user_content, response_text, current_time)
                    query_history.append({'query': user_content, 'type': rt, 'from_cache': False,
                                          'time_ms': api_time, 'timestamp': current_time})
                    dump_stats()
                    data['usage'] = data.get('usage', {})
                    data['usage']['cached'] = False
                    return data
                else:
                    dump_stats()
                    try:
                        err = resp.json()
                    except Exception:
                        err = {"error": resp.text}
                    return JSONResponse({"error": "Upstream error (" + str(resp.status_code) + ")", "detail": err}, status_code=502)

        except Exception as e:
            dump_stats()
            return JSONResponse({"error": "Relay error: " + str(e)}, status_code=502)

    except Exception as e:
        return JSONResponse({"error": "Internal error: " + str(e)}, status_code=500)


@app.get("/admin/config")
async def get_config():
    if config.get("upstream_key") and len(config["upstream_key"]) > 8:
        key_part = config["upstream_key"][:8] + "****"
    else:
        key_part = ""
    return {
        "sk": config["sk"],
        "upstream_url": config["upstream_url"],
        "upstream_key": key_part,
        "upstream_model": config["upstream_model"],
        "models": config.get("models", []),
        "port": config.get("port", 8001),
    }


@app.post("/admin/config")
async def set_config(request: Request):
    global config
    body = await request.json()
    if "upstream_url" in body:
        config["upstream_url"] = body["upstream_url"]
    if "upstream_key" in body:
        config["upstream_key"] = body["upstream_key"]
    if "upstream_model" in body:
        config["upstream_model"] = body["upstream_model"]
    if "models" in body:
        config["models"] = body["models"]
    _save_config(config)
    return {"success": True, "message": "配置已保存"}


@app.post("/admin/reset-sk")
async def reset_sk():
    global config
    config["sk"] = "sk-" + secrets.token_hex(24)
    _save_config(config)
    return {"success": True, "sk": config["sk"]}


@app.get("/api/metrics")
def get_metrics():
    dump_stats()
    try:
        with open(STATS_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'hit_rate': 0, 'cache_hits': 0, 'cache_misses': 0, 'total_requests': 0,
            'tokens_saved': 0, 'avg_response_time': 0, 'cache_hit_time': 10, 'cache_miss_time': 500,
            'l1_hits': 0, 'l2_hits': 0, 'l3_hits': 0, 'l2_size': 0, 'l3_size': 0,
            'semantic_cache_size': 0, 'hot_queries': [], 'code_generation': 0,
            'code_explanation': 0, 'debugging': 0, 'conversation': 0, 'general_qa': 0
        }


@app.get("/api/history")
def get_history(hours=24):
    try:
        hours = int(hours)
        cutoff = time.time() - hours * 3600
        recent = [q for q in query_history if q.get('timestamp', 0) >= cutoff]
        if not recent:
            try:
                c = sqlite3.connect(METRICS_DB)
                rows = c.execute("SELECT timestamp, total_requests, cache_hits, cache_misses, hit_rate, avg_response_time, tokens_saved, l1_hits, l2_hits, l3_hits FROM metrics_history WHERE timestamp >= ? ORDER BY timestamp ASC", (cutoff,)).fetchall()
                c.close()
                if rows:
                    keys = ['timestamp', 'total_requests', 'cache_hits', 'cache_misses', 'hit_rate', 'avg_response_time', 'tokens_saved', 'l1_hits', 'l2_hits', 'l3_hits']
                    h = [dict(zip(keys, r)) for r in rows]
                    return {
                        'timestamps': [datetime.fromtimestamp(r['timestamp']).isoformat() for r in h],
                        'hit_rates': [r['hit_rate'] * 100 for r in h],
                        'cache_hits': [1 if r['cache_hits'] > 0 else 0 for r in h],
                        'queries': []
                    }
            except Exception:
                pass
            return {'timestamps': [], 'hit_rates': [], 'cache_hits': [], 'queries': []}
        return {
            'timestamps': [datetime.fromtimestamp(q['timestamp']).isoformat() for q in recent],
            'hit_rates': [100.0 if q['from_cache'] else 0.0 for q in recent],
            'cache_hits': [1 if q['from_cache'] else 0 for q in recent],
            'queries': [(q.get('query', '')[:80] if q.get('query') else '') for q in recent]
        }
    except Exception as e:
        return {'timestamps': [], 'hit_rates': [], 'cache_hits': [], 'error': str(e)}


@app.get("/api/cache-levels")
def get_cache_levels():
    l1 = sum(1 for k, t in fast_cache_ttl.items() if time.time() - t < 300)
    return {'l1_hits': l1, 'l2_hits': len(fast_hash_cache) - l1, 'l3_hits': 0}


@app.get("/api/hot-queries")
def get_hot_queries():
    try:
        c = sqlite3.connect(CACHE_DB)
        rows = c.execute("SELECT query_text, hit_count FROM response_cache ORDER BY hit_count DESC LIMIT 10").fetchall()
        c.close()
        result = []
        for r in rows:
            result.append({'query': r[0][:80] if r[0] else '', 'hit_count': r[1]})
        return result
    except Exception:
        return []


# ===== 记忆系统 API =====

@app.get("/api/memory/stats")
def get_memory_stats():
    """获取记忆系统统计"""
    return memory_system.get_stats()


@app.get("/api/memory/list")
def list_memories(user_id: str = 'default', memory_type: str = None, limit: int = 50):
    """获取记忆列表"""
    return memory_system.get_all_memories(user_id, memory_type, limit)


@app.get("/api/memory/search")
def search_memories(query: str, user_id: str = 'default', memory_type: str = None, limit: int = 5):
    """搜索记忆"""
    return memory_system.search_memories(query, user_id, limit, memory_type)


@app.post("/api/memory/add")
async def add_memory(request: Request):
    """添加记忆"""
    body = await request.json()
    content = body.get('content', '')
    user_id = body.get('user_id', 'default')
    memory_type = body.get('memory_type', 'episodic')
    metadata = body.get('metadata', {})
    importance = body.get('importance', 0.5)
    
    if not content:
        return JSONResponse({'error': 'content is required'}, status_code=400)
    
    memory_id = memory_system.add_memory(content, user_id, memory_type, metadata, importance)
    return {'success': True, 'memory_id': memory_id}


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int):
    """删除记忆"""
    memory_system.delete_memory(memory_id)
    return {'success': True}


@app.post("/api/memory/clear")
async def clear_memories(request: Request):
    """清空记忆"""
    body = await request.json()
    user_id = body.get('user_id')
    memory_type = body.get('memory_type')
    memory_system.clear_memories(user_id, memory_type)
    return {'success': True}


# ===== 知识库 API =====

@app.get("/api/knowledge/list")
def list_knowledge(category: str = None, limit: int = 50):
    """获取知识列表"""
    return memory_system.get_all_knowledge(category, limit)


@app.get("/api/knowledge/search")
def search_knowledge(query: str, category: str = None, limit: int = 5):
    """搜索知识"""
    return memory_system.search_knowledge(query, category, limit)


@app.post("/api/knowledge/add")
async def add_knowledge(request: Request):
    """添加知识"""
    body = await request.json()
    title = body.get('title', '')
    content = body.get('content', '')
    category = body.get('category', 'general')
    tags = body.get('tags', [])
    source = body.get('source')
    
    if not title or not content:
        return JSONResponse({'error': 'title and content are required'}, status_code=400)
    
    knowledge_id = memory_system.add_knowledge(title, content, category, tags, source)
    return {'success': True, 'knowledge_id': knowledge_id}


@app.put("/api/knowledge/{knowledge_id}")
async def update_knowledge(knowledge_id: int, request: Request):
    """更新知识"""
    body = await request.json()
    title = body.get('title')
    content = body.get('content')
    tags = body.get('tags')
    memory_system.update_knowledge(knowledge_id, title, content, tags)
    return {'success': True}


@app.delete("/api/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id: int):
    """删除知识"""
    memory_system.delete_knowledge(knowledge_id)
    return {'success': True}


if __name__ == "__main__":
    port = config.get('port', 8001)
    print("Relay server: http://127.0.0.1:" + str(port))
    print("Dashboard:   http://127.0.0.1:" + str(port))
    print("SK key:      " + config["sk"])
    uvicorn.run(app, host="127.0.0.1", port=port)

