"""
自适应 TTL 管理器 - 根据访问模式动态调整缓存有效期
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics


class ContentType(Enum):
    """内容类型"""
    CODE = "code"
    CONVERSATION = "conversation"
    DOCUMENTATION = "documentation"
    GENERIC = "generic"


@dataclass
class TTLProfile:
    """TTL 配置文件"""
    content_type: ContentType
    base_ttl: int
    current_ttl: int
    min_ttl: int
    max_ttl: int
    hit_count: int = 0
    miss_count: int = 0
    access_history: List[float] = field(default_factory=list)
    hit_rate_history: List[float] = field(default_factory=list)
    last_adjustment: float = field(default_factory=time.time)
    
    def calculate_hit_rate(self, window: int = 10) -> float:
        """计算最近窗口期的命中率"""
        if not self.hit_rate_history:
            return 0.0
        recent = self.hit_rate_history[-window:]
        return statistics.mean(recent) if recent else 0.0
    
    def record_access(self, is_hit: bool) -> None:
        """记录访问"""
        current_time = time.time()
        self.access_history.append(current_time)
        
        # 只保留最近100次访问
        self.access_history = self.access_history[-100:]
        
        if is_hit:
            self.hit_count += 1
        else:
            self.miss_count += 1
        
        # 更新命中率历史
        total = self.hit_count + self.miss_count
        if total > 0:
            hit_rate = self.hit_count / total
            self.hit_rate_history.append(hit_rate)
            self.hit_rate_history = self.hit_rate_history[-50:]


class AdaptiveTTLManager:
    """自适应 TTL 管理器"""
    
    def __init__(
        self,
        min_ttl: int = 60,
        max_ttl: int = 604800,
        hit_threshold: int = 5,
        miss_threshold: int = 3,
        increment_factor: float = 1.5,
        decrement_factor: float = 0.7,
        adjustment_interval: int = 300
    ):
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self.hit_threshold = hit_threshold
        self.miss_threshold = miss_threshold
        self.increment_factor = increment_factor
        self.decrement_factor = decrement_factor
        self.adjustment_interval = adjustment_interval
        
        # 内容类型配置
        self._profiles: Dict[ContentType, TTLProfile] = {}
        self._init_profiles()
        
        # 查询到内容类型的映射
        self._query_types: Dict[str, ContentType] = {}
    
    def _init_profiles(self) -> None:
        """初始化各类型的 TTL 配置"""
        profiles_config = {
            ContentType.CODE: {
                'base_ttl': 3600,
                'min_ttl': 300,
                'max_ttl': 86400
            },
            ContentType.CONVERSATION: {
                'base_ttl': 1800,
                'min_ttl': 60,
                'max_ttl': 43200
            },
            ContentType.DOCUMENTATION: {
                'base_ttl': 86400,
                'min_ttl': 3600,
                'max_ttl': 604800
            },
            ContentType.GENERIC: {
                'base_ttl': 3600,
                'min_ttl': 60,
                'max_ttl': 86400
            }
        }
        
        for content_type, config in profiles_config.items():
            self._profiles[content_type] = TTLProfile(
                content_type=content_type,
                base_ttl=config['base_ttl'],
                current_ttl=config['base_ttl'],
                min_ttl=config['min_ttl'],
                max_ttl=config['max_ttl']
            )
    
    def _detect_content_type(self, query: str) -> ContentType:
        """检测内容类型"""
        query_lower = query.lower()
        
        # 代码相关关键词
        code_keywords = [
            'function', 'class', 'def', 'import', 'return', 'if', 'for', 'while',
            '代码', '函数', '类', '方法', '变量', 'bug', 'error', 'debug',
            'python', 'javascript', 'java', 'cpp', 'c++', 'go', 'rust'
        ]
        
        # 对话相关关键词
        conversation_keywords = [
            '你好', '请问', '谢谢', '帮助', 'how to', 'what is', 'explain',
            '为什么', '怎么做', '什么是', '介绍一下'
        ]
        
        # 文档相关关键词
        doc_keywords = [
            '文档', '说明', 'api', 'reference', 'guide', 'tutorial',
            'documentation', 'manual', 'specification'
        ]
        
        code_score = sum(1 for kw in code_keywords if kw in query_lower)
        conversation_score = sum(1 for kw in conversation_keywords if kw in query_lower)
        doc_score = sum(1 for kw in doc_keywords if kw in query_lower)
        
        scores = {
            ContentType.CODE: code_score,
            ContentType.CONVERSATION: conversation_score,
            ContentType.DOCUMENTATION: doc_score
        }
        
        best_type = max(scores, key=scores.get)
        
        # 如果没有明显特征，返回通用类型
        if scores[best_type] == 0:
            return ContentType.GENERIC
        
        return best_type
    
    def get_ttl(self, query: str) -> int:
        """获取查询的 TTL"""
        content_type = self._detect_content_type(query)
        self._query_types[query] = content_type
        
        profile = self._profiles[content_type]
        return profile.current_ttl
    
    def record_hit(self, query: str) -> None:
        """记录缓存命中"""
        content_type = self._query_types.get(query)
        if not content_type:
            content_type = self._detect_content_type(query)
        
        profile = self._profiles[content_type]
        profile.record_access(is_hit=True)
        
        # 检查是否需要调整 TTL
        self._maybe_adjust_ttl(profile)
    
    def record_miss(self, query: str) -> None:
        """记录缓存未命中"""
        content_type = self._query_types.get(query)
        if not content_type:
            content_type = self._detect_content_type(query)
        
        profile = self._profiles[content_type]
        profile.record_access(is_hit=False)
        
        # 检查是否需要调整 TTL
        self._maybe_adjust_ttl(profile)
    
    def _maybe_adjust_ttl(self, profile: TTLProfile) -> None:
        """根据需要调整 TTL"""
        current_time = time.time()
        
        # 检查调整间隔
        if current_time - profile.last_adjustment < self.adjustment_interval:
            return
        
        recent_hits = sum(
            1 for i, t in enumerate(profile.access_history)
            if t > current_time - self.adjustment_interval and 
            i >= len(profile.access_history) - self.hit_threshold
        )
        
        recent_misses = profile.miss_count
        
        # 如果命中次数多，增加 TTL
        if recent_hits >= self.hit_threshold:
            new_ttl = int(profile.current_ttl * self.increment_factor)
            profile.current_ttl = min(new_ttl, profile.max_ttl)
            profile.last_adjustment = current_time
            print(f"[AdaptiveTTL] Increased TTL for {profile.content_type.value}: "
                  f"{profile.current_ttl}s")
        
        # 如果未命中次数多，减少 TTL
        elif recent_misses >= self.miss_threshold:
            new_ttl = int(profile.current_ttl * self.decrement_factor)
            profile.current_ttl = max(new_ttl, profile.min_ttl)
            profile.last_adjustment = current_time
            print(f"[AdaptiveTTL] Decreased TTL for {profile.content_type.value}: "
                  f"{profile.current_ttl}s")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {}
        for content_type, profile in self._profiles.items():
            stats[content_type.value] = {
                'current_ttl': profile.current_ttl,
                'base_ttl': profile.base_ttl,
                'hit_count': profile.hit_count,
                'miss_count': profile.miss_count,
                'hit_rate': profile.calculate_hit_rate(),
                'last_adjustment': profile.last_adjustment
            }
        return stats
    
    def reset(self) -> None:
        """重置所有配置"""
        self._init_profiles()
        self._query_types.clear()
