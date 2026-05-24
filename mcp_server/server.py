"""
MCP Server - DeepSeek 缓存优化服务
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

from .cache.semantic import SemanticCache
from .cache.multi_level import MultiLevelCache
from .cache.adaptive_ttl import AdaptiveTTLManager
from agent.proxy import AgentProxy
from agent.decision import CacheDecisionEngine


class DeepSeekCacheServer:
    """DeepSeek 缓存 MCP 服务器"""
    
    def __init__(self):
        self.server = Server("deepseek-cache-optimizer")
        
        self.semantic_cache = SemanticCache(
            similarity_threshold=0.85,
            max_entries=10000
        )
        
        self.multi_level_cache = MultiLevelCache()
        self.ttl_manager = AdaptiveTTLManager()
        
        self.agent_proxy = AgentProxy()
        self.decision_engine = CacheDecisionEngine(min_confidence=0.8)
        
        self.request_history: List[Dict] = []
        self.max_history = 100
        
        self.metrics = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_response_time': 0,
            'tokens_saved': 0
        }
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置 MCP 处理器"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出可用工具"""
            return [
                Tool(
                    name="cache_query",
                    description="缓存查询 - 尝试从缓存获取响应",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "用户查询"
                            },
                            "context": {
                                "type": "string",
                                "description": "上下文信息（可选）"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="cache_store",
                    description="存储缓存 - 将查询和响应存入缓存",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "用户查询"
                            },
                            "response": {
                                "type": "string",
                                "description": "API 响应"
                            },
                            "ttl": {
                                "type": "integer",
                                "description": "缓存有效期（秒，可选）"
                            }
                        },
                        "required": ["query", "response"]
                    }
                ),
                Tool(
                    name="get_stats",
                    description="获取缓存统计信息",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="clear_cache",
                    description="清空缓存",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "description": "缓存级别 (l1/l2/l3/all)"
                            }
                        }
                    }
                ),
                Tool(
                    name="optimize_query",
                    description="优化查询 - 改写查询以提高缓存命中率",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "原始查询"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="predict_preload",
                    description="预测预加载 - 基于历史预测并预加载可能需要的缓存",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "current_query": {
                                "type": "string",
                                "description": "当前查询"
                            }
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
            """调用工具"""
            start_time = time.time()
            
            if name == "cache_query":
                result = await self._handle_cache_query(arguments)
            elif name == "cache_store":
                result = await self._handle_cache_store(arguments)
            elif name == "get_stats":
                result = await self._handle_get_stats()
            elif name == "clear_cache":
                result = await self._handle_clear_cache(arguments)
            elif name == "optimize_query":
                result = await self._handle_optimize_query(arguments)
            elif name == "predict_preload":
                result = await self._handle_predict_preload(arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            # 记录响应时间
            response_time = time.time() - start_time
            self.metrics['avg_response_time'] = (
                (self.metrics['avg_response_time'] * self.metrics['total_requests'] + response_time)
                / (self.metrics['total_requests'] + 1)
            )
            
            self._dump_stats_to_file()
            
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    
    async def _handle_cache_query(self, arguments: Dict) -> Dict:
        """处理缓存查询 - 通过 AgentProxy 归一化+改写以最大化命中率"""
        query = arguments.get("query", "")
        context = arguments.get("context", "")
        
        self.metrics['total_requests'] += 1
        self._record_request(query, context)
        
        best_hit = None
        best_similarity = 0
        tried_queries = []
        
        processed = self.agent_proxy.process_request(query, context)
        normalized = processed.normalized_query
        variants = self.agent_proxy.rewrite_for_cache(query, similarity_threshold=0.75)
        
        all_queries = [normalized]
        for v in variants:
            if v not in all_queries:
                all_queries.append(v)
        
        for q in all_queries:
            tried_queries.append(q)
            cache_result = self.semantic_cache.get(q)
            if cache_result:
                matched_query, similarity, response = cache_result
                if similarity > best_similarity:
                    best_hit = (matched_query, similarity, response)
                    best_similarity = similarity
        
        if best_hit and best_similarity >= 0.75:
            matched_query, similarity, response = best_hit
            self.metrics['cache_hits'] += 1
            self.ttl_manager.record_hit(query)
            
            return {
                "cache_hit": True,
                "source": "semantic_cache",
                "matched_query": matched_query,
                "similarity": similarity,
                "response": response,
                "tokens_saved": len(response) // 4,
                "optimized": normalized != query,
                "variants_tried": len(tried_queries)
            }
        
        cache_key = processed.cache_key
        ml_result = self.multi_level_cache.get(cache_key)
        
        if ml_result:
            self.metrics['cache_hits'] += 1
            self.ttl_manager.record_hit(query)
            
            return {
                "cache_hit": True,
                "source": "multi_level_cache",
                "response": ml_result,
                "tokens_saved": len(str(ml_result)) // 4
            }
        
        self.metrics['cache_misses'] += 1
        self.ttl_manager.record_miss(query)
        
        return {
            "cache_hit": False,
            "message": "缓存未命中，需要调用 API"
        }
    
    async def _handle_cache_store(self, arguments: Dict) -> Dict:
        """处理缓存存储 - 通过 AgentProxy 归一化"""
        query = arguments.get("query", "")
        response = arguments.get("response", "")
        ttl = arguments.get("ttl")
        
        processed = self.agent_proxy.process_request(query)
        normalized = processed.normalized_query
        
        if ttl is None:
            ttl = self.ttl_manager.get_ttl(query)
        
        self.semantic_cache.set(normalized, response, ttl)
        
        cache_key = processed.cache_key
        self.multi_level_cache.set(cache_key, response, ttl)
        
        self.metrics['tokens_saved'] += len(response) // 4
        
        return {
            "success": True,
            "ttl": ttl,
            "normalized_query": normalized if normalized != query else query,
            "message": f"缓存已存储，TTL: {ttl}秒"
        }
    
    async def _handle_get_stats(self) -> Dict:
        """获取统计信息"""
        semantic_stats = self.semantic_cache.get_stats()
        ml_stats = self.multi_level_cache.get_stats()
        ttl_stats = self.ttl_manager.get_stats()
        
        total = self.metrics['total_requests']
        hit_rate = self.metrics['cache_hits'] / total if total > 0 else 0
        
        return {
            "overview": {
                "total_requests": self.metrics['total_requests'],
                "cache_hits": self.metrics['cache_hits'],
                "cache_misses": self.metrics['cache_misses'],
                "hit_rate": round(hit_rate * 100, 2),
                "avg_response_time_ms": round(self.metrics['avg_response_time'] * 1000, 2),
                "tokens_saved_estimate": self.metrics['tokens_saved']
            },
            "semantic_cache": semantic_stats,
            "multi_level_cache": ml_stats,
            "adaptive_ttl": ttl_stats
        }
    
    def _dump_stats_to_file(self):
        try:
            stats_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
            os.makedirs(stats_dir, exist_ok=True)
            stats_path = os.path.join(stats_dir, 'cache_stats.json')
            
            semantic_stats = self.semantic_cache.get_stats()
            ml_stats = self.multi_level_cache.get_stats()
            agent_stats = self.agent_proxy.get_stats()
            
            total = self.metrics['total_requests']
            hit_rate = self.metrics['cache_hits'] / total if total > 0 else 0
            
            stats = {
                'timestamp': time.time(),
                'hit_rate': hit_rate,
                'cache_hits': self.metrics['cache_hits'],
                'cache_misses': self.metrics['cache_misses'],
                'total_requests': total,
                'tokens_saved': self.metrics['tokens_saved'],
                'avg_response_time': round(self.metrics['avg_response_time'] * 1000, 2),
                'l1_hits': ml_stats.get('l1_hits', 0),
                'l2_hits': ml_stats.get('l2_hits', 0),
                'l3_hits': ml_stats.get('l3_hits', 0),
                'l1_size': ml_stats.get('l1', {}).get('size', 0) if isinstance(ml_stats.get('l1'), dict) else 0,
                'l2_size': ml_stats.get('l2', {}).get('size', 0) if isinstance(ml_stats.get('l2'), dict) else 0,
                'l3_size': ml_stats.get('l3', {}).get('size', 0) if isinstance(ml_stats.get('l3'), dict) else 0,
                'semantic_cache_size': semantic_stats.get('cache_size', 0),
                'hot_queries': semantic_stats.get('hot_queries', []),
                'agent_normalized': agent_stats.get('normalized_requests', 0),
                'agent_cacheable': agent_stats.get('cached_requests', 0),
            }
            
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False)
        except Exception:
            pass
    
    async def _handle_clear_cache(self, arguments: Dict) -> Dict:
        """清空缓存"""
        level = arguments.get("level", "all")
        
        if level == "all" or level == "semantic":
            if self.semantic_cache:
                self.semantic_cache.clear()
        
        # 注意：多级缓存的清空需要单独实现
        
        return {
            "success": True,
            "message": f"缓存已清空 (level: {level})"
        }
    
    async def _handle_optimize_query(self, arguments: Dict) -> Dict:
        query = arguments.get("query", "")
        
        processed = self.agent_proxy.process_request(query)
        variants = self.agent_proxy.rewrite_for_cache(query)
        
        similar = []
        for v in variants:
            hit = self.semantic_cache.get(v)
            if hit:
                similar.append({
                    "variant": v,
                    "matched": hit[0],
                    "similarity": hit[1]
                })
        
        return {
            "original_query": query,
            "normalized_query": processed.normalized_query,
            "request_type": processed.metadata.get("request_type"),
            "variants": variants,
            "similar_cached": similar,
            "suggestions": self._generate_suggestions(query)
        }
    
    async def _handle_predict_preload(self, arguments: Dict) -> Dict:
        current_query = arguments.get("current_query", "")
        recent = [r["query"] for r in self.request_history[-10:]]
        
        predictions = self.decision_engine.should_preload(
            current_query, recent, pattern_confidence=0.6
        )
        
        return {
            "current_query": current_query,
            "predictions": [{"query": q, "confidence": c} for q, c in predictions],
            "preloaded_count": len(predictions)
        }
    
    def _generate_cache_key(self, query: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def _record_request(self, query: str, context: str) -> None:
        """记录请求历史"""
        self.request_history.append({
            "query": query,
            "context": context,
            "timestamp": time.time()
        })
        
        # 限制历史大小
        if len(self.request_history) > self.max_history:
            self.request_history = self.request_history[-self.max_history:]
    
    def _normalize_query(self, query: str) -> str:
        """归一化查询"""
        import re
        # 去除多余空白
        normalized = re.sub(r'\s+', ' ', query).strip()
        # 转换为小写
        normalized = normalized.lower()
        return normalized
    
    def _find_similar_query(self, query: str) -> Optional[str]:
        """查找相似的已缓存查询"""
        # 这里简化处理，实际应该使用向量相似度
        for entry in self.request_history[-20:]:
            if query in entry["query"] or entry["query"] in query:
                return entry["query"]
        return None
    
    def _generate_suggestions(self, query: str) -> List[str]:
        """生成查询优化建议"""
        suggestions = []
        
        # 检查是否有常见模式
        if "how to" in query.lower():
            suggestions.append("考虑使用更具体的动词，如 'implement', 'create', 'build'")
        
        if len(query) > 200:
            suggestions.append("查询较长，考虑提取核心问题")
        
        if "?" not in query:
            suggestions.append("明确问题的结尾，使用问号")
        
        return suggestions
    
    def _predict_next_queries(self, current_query: str) -> List[str]:
        """预测下一个可能的查询"""
        predictions = []
        
        # 基于历史模式预测
        if not self.request_history:
            return predictions
        
        # 找到相似的历史查询
        similar_queries = [
            entry["query"] for entry in self.request_history
            if any(word in entry["query"] for word in current_query.split())
            and entry["query"] != current_query
        ]
        
        # 返回最常见的相关查询
        from collections import Counter
        query_counts = Counter(similar_queries)
        predictions = [q for q, _ in query_counts.most_common(5)]
        
        return predictions
    
    async def run(self):
        """运行服务器"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """主入口"""
    server = DeepSeekCacheServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
