"""
MCP Server with Skills - 集成 Skill 系统的 MCP 服务
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 导入原有模块
from .cache.semantic import SemanticCache
from .cache.multi_level import MultiLevelCache
from .cache.adaptive_ttl import AdaptiveTTLManager

# 导入 Skill 模块
from skills.mcp_integration import mcp_skill_integration


class DeepSeekCacheServerWithSkills:
    """集成 Skill 的 DeepSeek 缓存 MCP 服务器"""
    
    def __init__(self):
        self.server = Server("deepseek-cache-optimizer")
        
        # 初始化缓存组件
        self.semantic_cache = SemanticCache(
            similarity_threshold=0.85,
            max_entries=10000
        )
        self.multi_level_cache = MultiLevelCache()
        self.ttl_manager = AdaptiveTTLManager()
        
        # 请求历史
        self.request_history: List[Dict] = []
        self.max_history = 100
        
        # 性能指标
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
            tools = []
            
            # 原有工具
            tools.extend([
                Tool(
                    name="cache_query",
                    description="缓存查询 - 尝试从缓存获取响应",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "用户查询"},
                            "context": {"type": "string", "description": "上下文信息（可选）"}
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
                            "query": {"type": "string", "description": "用户查询"},
                            "response": {"type": "string", "description": "API 响应"},
                            "ttl": {"type": "integer", "description": "缓存有效期（秒，可选）"}
                        },
                        "required": ["query", "response"]
                    }
                ),
                Tool(
                    name="get_stats",
                    description="获取缓存统计信息",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="clear_cache",
                    description="清空缓存",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "level": {"type": "string", "description": "缓存级别 (l1/l2/l3/all)"}
                        }
                    }
                ),
                Tool(
                    name="optimize_query",
                    description="优化查询 - 改写查询以提高缓存命中率",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "原始查询"}
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
                            "current_query": {"type": "string", "description": "当前查询"}
                        }
                    }
                ),
            ])
            
            # 添加 Skill 工具
            tools.extend(mcp_skill_integration.get_tools())
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
            """调用工具"""
            # Skill 工具
            skill_tools = ['skill_execute', 'skill_list', 'skill_help', 'skill_parse']
            if name in skill_tools:
                return await mcp_skill_integration.execute_tool(name, arguments)
            
            # 原有工具
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
            
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    
    # 原有处理方法...
    async def _handle_cache_query(self, arguments: Dict) -> Dict:
        """处理缓存查询"""
        query = arguments.get("query", "")
        context = arguments.get("context", "")
        
        self.metrics['total_requests'] += 1
        self._record_request(query, context)
        
        # 尝试语义缓存
        cache_result = self.semantic_cache.get(query)
        
        if cache_result:
            matched_query, similarity, response = cache_result
            self.metrics['cache_hits'] += 1
            self.ttl_manager.record_hit(query)
            
            return {
                "cache_hit": True,
                "source": "semantic_cache",
                "matched_query": matched_query,
                "similarity": similarity,
                "response": response,
                "tokens_saved": len(response) // 4
            }
        
        # 尝试多级缓存
        cache_key = self._generate_cache_key(query)
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
        """处理缓存存储"""
        query = arguments.get("query", "")
        response = arguments.get("response", "")
        ttl = arguments.get("ttl")
        
        if ttl is None:
            ttl = self.ttl_manager.get_ttl(query)
        
        self.semantic_cache.set(query, response, ttl)
        cache_key = self._generate_cache_key(query)
        self.multi_level_cache.set(cache_key, response, ttl)
        
        self.metrics['tokens_saved'] += len(response) // 4
        
        return {
            "success": True,
            "ttl": ttl,
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
    
    async def _handle_clear_cache(self, arguments: Dict) -> Dict:
        """清空缓存"""
        level = arguments.get("level", "all")
        
        if level == "all" or level == "semantic":
            self.semantic_cache.clear()
        
        return {
            "success": True,
            "message": f"缓存已清空 (level: {level})"
        }
    
    async def _handle_optimize_query(self, arguments: Dict) -> Dict:
        """优化查询"""
        from agent.proxy import AgentProxy
        
        query = arguments.get("query", "")
        proxy = AgentProxy()
        result = proxy.process_request(query)
        
        return {
            "original_query": result.original_query,
            "normalized_query": result.normalized_query,
            "cache_key": result.cache_key,
            "should_cache": result.should_cache,
            "priority": result.priority,
            "metadata": result.metadata
        }
    
    async def _handle_predict_preload(self, arguments: Dict) -> Dict:
        """预测预加载"""
        from agent.decision import CacheDecisionEngine
        
        current_query = arguments.get("current_query", "")
        engine = CacheDecisionEngine()
        
        recent_queries = [r["query"] for r in self.request_history[-10:]]
        predictions = engine.should_preload(current_query, recent_queries)
        
        return {
            "current_query": current_query,
            "predictions": [
                {"query": q, "confidence": conf} for q, conf in predictions
            ],
            "prediction_count": len(predictions)
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
        
        if len(self.request_history) > self.max_history:
            self.request_history = self.request_history[-self.max_history:]
    
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
    server = DeepSeekCacheServerWithSkills()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
