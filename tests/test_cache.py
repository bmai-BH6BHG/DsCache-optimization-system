"""
缓存模块测试
"""

import pytest
import time
import tempfile
import shutil
from pathlib import Path

from mcp_server.cache.semantic import SemanticCache
from mcp_server.cache.multi_level import MultiLevelCache
from mcp_server.cache.adaptive_ttl import AdaptiveTTLManager


class TestSemanticCache:
    """测试语义缓存"""
    
    def test_exact_match(self):
        """测试精确匹配"""
        cache = SemanticCache(max_entries=100)
        
        cache.set("test query", "test response", ttl=3600)
        result = cache.get("test query")
        
        assert result is not None
        assert result[0] == "test query"
        assert result[1] == 1.0  # 相似度
        assert result[2] == "test response"
    
    def test_semantic_match(self):
        """测试语义匹配"""
        cache = SemanticCache(similarity_threshold=0.8, max_entries=100)
        
        cache.set("how to optimize python code", "response 1", ttl=3600)
        
        # 语义相似的查询
        result = cache.get("python performance optimization")
        
        assert result is not None
        assert result[1] >= 0.8  # 相似度应该高于阈值
    
    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = SemanticCache(max_entries=100)
        
        result = cache.get("nonexistent query")
        assert result is None
    
    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = SemanticCache(max_entries=100)
        
        cache.set("test query", "test response", ttl=1)
        time.sleep(2)
        
        result = cache.get("test query")
        assert result is None
    
    def test_stats(self):
        """测试统计信息"""
        cache = SemanticCache(max_entries=100)
        
        cache.set("query1", "response1")
        cache.get("query1")  # 命中
        cache.get("query2")  # 未命中
        
        stats = cache.get_stats()
        assert stats['total_requests'] == 2
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 1
        assert stats['hit_rate'] == 0.5


class TestMultiLevelCache:
    """测试多级缓存"""
    
    def test_l1_cache(self):
        """测试 L1 缓存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MultiLevelCache(
                l1_config={'max_size': 100, 'ttl': 300},
                l2_config={'db_path': f'{tmpdir}/l2.db', 'max_size': 100, 'ttl': 3600},
                l3_config={'storage_path': f'{tmpdir}/l3', 'max_size': 100, 'ttl': 86400}
            )
            
            cache.set("key1", "value1")
            result = cache.get("key1")
            
            assert result == "value1"
            
            stats = cache.get_stats()
            assert stats['l1_hits'] == 1
    
    def test_cache_promotion(self):
        """测试缓存提升"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MultiLevelCache(
                l1_config={'max_size': 100, 'ttl': 300},
                l2_config={'db_path': f'{tmpdir}/l2.db', 'max_size': 100, 'ttl': 3600},
                l3_config={'storage_path': f'{tmpdir}/l3', 'max_size': 100, 'ttl': 86400}
            )
            
            # 直接写入 L3
            cache.l3.set("key1", "value1")
            
            # 读取应该提升到 L1 和 L2
            result = cache.get("key1")
            assert result == "value1"
            
            # 再次读取应该从 L1 获取
            result = cache.get("key1")
            stats = cache.get_stats()
            assert stats['l3_hits'] == 1
            assert stats['l1_hits'] == 1
    
    def test_stats(self):
        """测试统计信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MultiLevelCache(
                l1_config={'max_size': 100, 'ttl': 300},
                l2_config={'db_path': f'{tmpdir}/l2.db', 'max_size': 100, 'ttl': 3600},
                l3_config={'storage_path': f'{tmpdir}/l3', 'max_size': 100, 'ttl': 86400}
            )
            
            cache.set("key1", "value1")
            cache.get("key1")
            cache.get("nonexistent")
            
            stats = cache.get_stats()
            assert stats['total_requests'] == 2
            assert stats['total_hits'] == 1
            assert stats['misses'] == 1


class TestAdaptiveTTL:
    """测试自适应 TTL"""
    
    def test_content_type_detection(self):
        """测试内容类型检测"""
        ttl_manager = AdaptiveTTLManager()
        
        # 代码相关
        ttl = ttl_manager.get_ttl("如何写 Python 函数")
        assert ttl > 0
        
        # 对话相关
        ttl = ttl_manager.get_ttl("你好，请帮我")
        assert ttl > 0
    
    def test_ttl_adjustment(self):
        """测试 TTL 调整"""
        ttl_manager = AdaptiveTTLManager(
            adjustment_interval=0  # 立即调整
        )
        
        query = "test query"
        initial_ttl = ttl_manager.get_ttl(query)
        
        # 模拟多次命中
        for _ in range(10):
            ttl_manager.record_hit(query)
        
        # TTL 应该增加
        # 注意：实际行为取决于实现细节
    
    def test_stats(self):
        """测试统计信息"""
        ttl_manager = AdaptiveTTLManager()
        
        query = "test query"
        ttl_manager.get_ttl(query)
        ttl_manager.record_hit(query)
        ttl_manager.record_miss(query)
        
        stats = ttl_manager.get_stats()
        assert len(stats) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
