"""
智能体模块测试
"""

import pytest
from agent.proxy import AgentProxy
from agent.context import ContextManager
from agent.decision import CacheDecisionEngine, CacheDecision


class TestAgentProxy:
    """测试智能体代理"""
    
    def test_normalize_query(self):
        """测试查询归一化"""
        proxy = AgentProxy()
        
        # 测试空白字符归一化
        result = proxy._normalize_query("  hello   world  ")
        assert result == "hello world"
        
        # 测试大小写转换
        result = proxy._normalize_query("Hello World")
        assert "hello" in result
    
    def test_detect_request_type(self):
        """测试请求类型检测"""
        proxy = AgentProxy()
        
        # 代码生成
        req_type = proxy._detect_request_type("写一个 Python 函数")
        assert req_type == "code_generation"
        
        # 调试
        req_type = proxy._detect_request_type("这个 bug 怎么修复")
        assert req_type == "debugging"
        
        # 对话
        req_type = proxy._detect_request_type("你好，请帮我")
        assert req_type == "conversation"
    
    def test_contains_code(self):
        """测试代码检测"""
        proxy = AgentProxy()
        
        assert proxy._contains_code("```python\ndef foo():\n```")
        assert proxy._contains_code("`code`")
        assert proxy._contains_code("def function_name")
        assert not proxy._contains_code("hello world")
    
    def test_process_request(self):
        """测试请求处理"""
        proxy = AgentProxy()
        
        result = proxy.process_request(
            query="如何优化 Python 代码？",
            context="file: main.py"
        )
        
        assert result.original_query == "如何优化 Python 代码？"
        assert result.normalized_query is not None
        assert result.cache_key is not None
        assert isinstance(result.should_cache, bool)
        assert result.priority > 0
        assert result.metadata is not None
    
    def test_should_cache_request(self):
        """测试缓存决策"""
        proxy = AgentProxy()
        
        # 太短的查询
        assert not proxy._should_cache_request("hi", "general_qa")
        
        # 包含敏感信息
        assert not proxy._should_cache_request("password = 123456", "general_qa")
        
        # 正常查询
        assert proxy._should_cache_request("如何优化 Python 代码", "general_qa")
    
    def test_rewrite_for_cache(self):
        """测试查询改写"""
        proxy = AgentProxy()
        
        variations = proxy.rewrite_for_cache("请问如何优化代码？谢谢！")
        
        assert len(variations) > 0
        # 应该去除礼貌用语
        assert any("请问" not in v for v in variations)


class TestContextManager:
    """测试上下文管理器"""
    
    def test_add_turn(self):
        """测试添加对话回合"""
        manager = ContextManager()
        
        manager.add_turn("user", "hello")
        manager.add_turn("assistant", "hi")
        
        assert len(manager.conversation_history) == 2
    
    def test_get_relevant_context(self):
        """测试获取相关上下文"""
        manager = ContextManager()
        
        manager.add_turn("user", "Python 性能优化")
        manager.add_turn("assistant", "可以使用缓存")
        
        context = manager.get_relevant_context("Python 缓存优化")
        assert "Python" in context
    
    def test_update_code_context(self):
        """测试更新代码上下文"""
        manager = ContextManager()
        
        manager.update_code_context(
            file_path="main.py",
            language="python",
            content="def foo(): pass"
        )
        
        assert manager.current_code_context is not None
        assert manager.current_code_context.file_path == "main.py"
    
    def test_get_context_hash(self):
        """测试上下文哈希"""
        manager = ContextManager()
        
        manager.add_turn("user", "test")
        hash1 = manager.get_context_hash()
        
        manager.add_turn("assistant", "response")
        hash2 = manager.get_context_hash()
        
        assert hash1 != hash2


class TestCacheDecisionEngine:
    """测试缓存决策引擎"""
    
    def test_decide_use_cache(self):
        """测试使用缓存决策"""
        engine = CacheDecisionEngine()
        
        result = engine.decide(
            query="test",
            cache_hit=True,
            cache_age=100,
            query_similarity=0.95
        )
        
        assert result.decision == CacheDecision.USE_CACHE
        assert result.confidence > 0.8
    
    def test_decide_refresh_cache(self):
        """测试刷新缓存决策"""
        engine = CacheDecisionEngine()
        
        # 缓存太旧
        result = engine.decide(
            query="test",
            cache_hit=True,
            cache_age=100000,  # 很旧
            query_similarity=0.95
        )
        
        assert result.decision == CacheDecision.REFRESH_CACHE
    
    def test_decide_skip_cache(self):
        """测试跳过缓存决策"""
        engine = CacheDecisionEngine()
        
        result = engine.decide(
            query="test",
            cache_hit=False
        )
        
        assert result.decision == CacheDecision.SKIP_CACHE
    
    def test_user_preference(self):
        """测试用户偏好"""
        engine = CacheDecisionEngine()
        
        # 用户要求最新内容
        result = engine.decide(
            query="test",
            cache_hit=True,
            user_preference="fresh"
        )
        assert result.decision == CacheDecision.REFRESH_CACHE
        
        # 用户要求快速响应
        result = engine.decide(
            query="test",
            cache_hit=True,
            user_preference="fast"
        )
        assert result.decision == CacheDecision.USE_CACHE
    
    def test_should_preload(self):
        """测试预加载判断"""
        engine = CacheDecisionEngine()
        
        predictions = engine.should_preload(
            current_query="Python 函数",
            recent_queries=[
                "Python 类",
                "Python 模块",
                "Python 包"
            ]
        )
        
        # 应该返回预测列表
        assert isinstance(predictions, list)
    
    def test_freshness_calculation(self):
        """测试新鲜度计算"""
        engine = CacheDecisionEngine()
        
        # 新缓存
        assert engine._calculate_freshness(100) > 0.8
        
        # 旧缓存
        assert engine._calculate_freshness(100000) < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
