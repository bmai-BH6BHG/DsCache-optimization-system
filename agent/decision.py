"""
缓存决策引擎 - 智能判断何时使用缓存
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import random


class CacheDecision(Enum):
    """缓存决策"""
    USE_CACHE = "use_cache"
    REFRESH_CACHE = "refresh_cache"
    SKIP_CACHE = "skip_cache"
    PREDICT_PRELOAD = "predict_preload"


@dataclass
class DecisionResult:
    """决策结果"""
    decision: CacheDecision
    confidence: float
    reason: str
    metadata: Dict[str, Any]


class CacheDecisionEngine:
    """缓存决策引擎"""
    
    def __init__(
        self,
        min_confidence: float = 0.8,
        max_retries: int = 3,
        fallback_to_api: bool = True
    ):
        self.min_confidence = min_confidence
        self.max_retries = max_retries
        self.fallback_to_api = fallback_to_api
        
        # 决策历史
        self.decision_history: List[Dict] = []
        self.max_history = 100
        
        # 性能统计
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'refresh_requests': 0,
            'skip_requests': 0,
            'avg_confidence': 0.0
        }
    
    def decide(
        self,
        query: str,
        cache_hit: bool,
        cache_age: Optional[float] = None,
        query_similarity: float = 1.0,
        context_changed: bool = False,
        user_preference: Optional[str] = None
    ) -> DecisionResult:
        """
        做出缓存决策
        
        Args:
            query: 用户查询
            cache_hit: 是否命中缓存
            cache_age: 缓存年龄（秒）
            query_similarity: 查询相似度
            context_changed: 上下文是否变化
            user_preference: 用户偏好（如 'fresh', 'fast'）
        
        Returns:
            DecisionResult: 决策结果
        """
        # 1. 如果用户明确偏好，优先使用
        if user_preference == 'fresh':
            return DecisionResult(
                decision=CacheDecision.REFRESH_CACHE,
                confidence=1.0,
                reason="用户要求最新内容",
                metadata={'user_preference': user_preference}
            )
        
        if user_preference == 'fast':
            if cache_hit:
                return DecisionResult(
                    decision=CacheDecision.USE_CACHE,
                    confidence=1.0,
                    reason="用户要求快速响应",
                    metadata={'user_preference': user_preference}
                )
        
        # 2. 检查上下文变化
        if context_changed:
            return DecisionResult(
                decision=CacheDecision.REFRESH_CACHE,
                confidence=0.9,
                reason="上下文已变化，需要刷新",
                metadata={'context_changed': True}
            )
        
        # 3. 如果没有命中缓存
        if not cache_hit:
            self.stats['cache_misses'] += 1
            return DecisionResult(
                decision=CacheDecision.SKIP_CACHE,
                confidence=1.0,
                reason="缓存未命中",
                metadata={'cache_hit': False}
            )
        
        # 4. 检查缓存新鲜度
        if cache_age is not None:
            freshness_score = self._calculate_freshness(cache_age)
            
            if freshness_score < 0.3:
                self.stats['refresh_requests'] += 1
                return DecisionResult(
                    decision=CacheDecision.REFRESH_CACHE,
                    confidence=0.85,
                    reason=f"缓存较旧 ({cache_age:.0f}秒)",
                    metadata={'cache_age': cache_age, 'freshness_score': freshness_score}
                )
        
        # 5. 检查查询相似度
        if query_similarity < 0.9:
            confidence = query_similarity
            if confidence < self.min_confidence:
                return DecisionResult(
                    decision=CacheDecision.REFRESH_CACHE,
                    confidence=1 - confidence,
                    reason=f"查询相似度较低 ({query_similarity:.2f})",
                    metadata={'query_similarity': query_similarity}
                )
        
        # 6. 使用缓存
        self.stats['cache_hits'] += 1
        confidence = min(query_similarity, 0.95)
        
        # 更新平均置信度
        self._update_avg_confidence(confidence)
        
        return DecisionResult(
            decision=CacheDecision.USE_CACHE,
            confidence=confidence,
            reason="缓存命中且条件满足",
            metadata={
                'cache_hit': True,
                'cache_age': cache_age,
                'query_similarity': query_similarity
            }
        )
    
    def _calculate_freshness(self, age: float) -> float:
        """计算缓存新鲜度分数 (0-1)"""
        # 使用指数衰减
        # 1小时内: 高新鲜度
        # 1-24小时: 中等新鲜度
        # 24小时以上: 低新鲜度
        
        if age < 3600:  # 1小时
            return 1.0 - (age / 3600) * 0.2
        elif age < 86400:  # 24小时
            return 0.8 - ((age - 3600) / 82800) * 0.5
        else:
            return max(0.1, 0.3 - (age - 86400) / 86400 * 0.2)
    
    def _update_avg_confidence(self, confidence: float) -> None:
        """更新平均置信度"""
        n = self.stats['cache_hits']
        self.stats['avg_confidence'] = (
            (self.stats['avg_confidence'] * (n - 1) + confidence) / n
            if n > 0 else confidence
        )
    
    def should_preload(
        self,
        current_query: str,
        recent_queries: List[str],
        pattern_confidence: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        判断是否应该预加载某些查询
        
        Returns:
            List of (query, confidence) tuples
        """
        if len(recent_queries) < 3:
            return []
        
        predictions = []
        
        # 1. 基于序列模式预测
        sequence_preds = self._predict_from_sequence(recent_queries)
        predictions.extend(sequence_preds)
        
        # 2. 基于主题相关性预测
        topic_preds = self._predict_from_topic(current_query, recent_queries)
        predictions.extend(topic_preds)
        
        # 3. 过滤并排序
        filtered = [
            (q, conf) for q, conf in predictions
            if conf >= pattern_confidence and q not in recent_queries
        ]
        
        # 去重并取前5个
        seen = set()
        unique_preds = []
        for q, conf in sorted(filtered, key=lambda x: x[1], reverse=True):
            if q not in seen:
                seen.add(q)
                unique_preds.append((q, conf))
                if len(unique_preds) >= 5:
                    break
        
        return unique_preds
    
    def _predict_from_sequence(
        self, 
        recent_queries: List[str]
    ) -> List[Tuple[str, float]]:
        """从序列模式预测"""
        predictions = []
        
        # 简单的 n-gram 预测
        if len(recent_queries) >= 2:
            # 检查是否有常见模式
            last_two = ' | '.join(recent_queries[-2:])
            
            # 编程相关序列
            if 'function' in last_two.lower() or 'def ' in last_two:
                predictions.append(("如何调用这个函数？", 0.6))
                predictions.append(("这个函数的参数是什么？", 0.5))
            
            if 'error' in last_two.lower() or 'bug' in last_two:
                predictions.append(("如何修复这个错误？", 0.7))
                predictions.append(("这个错误的原因是什么？", 0.6))
            
            if 'import' in last_two.lower():
                predictions.append(("这个库的其他用法", 0.5))
        
        return predictions
    
    def _predict_from_topic(
        self,
        current_query: str,
        recent_queries: List[str]
    ) -> List[Tuple[str, float]]:
        """从主题相关性预测"""
        predictions = []
        
        # 提取当前查询的关键词
        current_words = set(current_query.lower().split())
        
        # 找到相关历史查询
        for query in recent_queries[:-1]:  # 排除当前查询
            query_words = set(query.lower().split())
            overlap = len(current_words & query_words)
            
            if overlap > 0:
                confidence = min(0.8, overlap / len(current_words) + 0.3)
                
                # 生成相关查询
                related = self._generate_related_query(query, current_query)
                if related:
                    predictions.append((related, confidence))
        
        return predictions
    
    def _generate_related_query(
        self, 
        base_query: str, 
        current_query: str
    ) -> Optional[str]:
        """生成相关查询"""
        # 简单实现：提取共同主题 + 常见问题
        common_patterns = [
            "最佳实践是什么",
            "有什么注意事项",
            "性能如何优化",
            "常见错误有哪些",
            "相关概念是什么"
        ]
        
        # 随机选择一个模式
        pattern = random.choice(common_patterns)
        
        # 尝试提取主题
        words = set(base_query.lower().split()) & set(current_query.lower().split())
        if words:
            topic = ' '.join(list(words)[:3])
            return f"{topic} {pattern}"
        
        return None
    
    def record_decision(self, result: DecisionResult, actual_outcome: str) -> None:
        """记录决策结果用于学习"""
        self.decision_history.append({
            'decision': result.decision.value,
            'confidence': result.confidence,
            'reason': result.reason,
            'outcome': actual_outcome,
            'timestamp': time.time()
        })
        
        # 限制历史大小
        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history:]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = self.stats['cache_hits'] / total if total > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': hit_rate,
            'total_decisions': total,
            'decision_history_size': len(self.decision_history)
        }
