"""
语义缓存模块 - 基于向量相似度的智能缓存
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import jieba
import re


@dataclass
class CacheEntry:
    """缓存条目"""
    query: str
    response: str
    embedding: np.ndarray
    timestamp: float
    hit_count: int = 0
    access_times: List[float] = None
    ttl: int = 3600
    
    def __post_init__(self):
        if self.access_times is None:
            self.access_times = []
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'query': self.query,
            'response': self.response,
            'embedding': self.embedding.tolist(),
            'timestamp': self.timestamp,
            'hit_count': self.hit_count,
            'access_times': self.access_times,
            'ttl': self.ttl
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CacheEntry':
        """从字典创建"""
        return cls(
            query=data['query'],
            response=data['response'],
            embedding=np.array(data['embedding']),
            timestamp=data['timestamp'],
            hit_count=data.get('hit_count', 0),
            access_times=data.get('access_times', []),
            ttl=data.get('ttl', 3600)
        )


class SemanticCache:
    """语义缓存类"""
    
    def __init__(
        self,
        model_name: str = "H:\\huggingface_cache\\hub\\models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2\\snapshots\\e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
        similarity_threshold: float = 0.85,
        device: str = "cpu",
        max_entries: int = 10000
    ):
        self.model = SentenceTransformer(model_name, device=device)
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        
        # 缓存存储
        self._cache: Dict[str, CacheEntry] = {}
        self._embeddings: List[np.ndarray] = []
        self._keys: List[str] = []
        
        # 统计信息
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'semantic_hits': 0,
            'exact_hits': 0
        }
    
    def _normalize_text(self, text: str) -> str:
        """文本归一化"""
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 转换为小写
        text = text.lower()
        return text
    
    def _generate_key(self, text: str) -> str:
        """生成缓存键"""
        normalized = self._normalize_text(text)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _compute_embedding(self, text: str) -> np.ndarray:
        """计算文本嵌入向量"""
        normalized = self._normalize_text(text)
        embedding = self.model.encode(normalized, convert_to_numpy=True)
        return embedding
    
    def _find_similar(
        self, 
        query_embedding: np.ndarray
    ) -> Optional[Tuple[str, float]]:
        """查找相似缓存条目"""
        if not self._embeddings:
            return None
        
        # 计算相似度
        embeddings_array = np.array(self._embeddings)
        similarities = cosine_similarity(
            [query_embedding], 
            embeddings_array
        )[0]
        
        # 找到最相似的
        max_idx = np.argmax(similarities)
        max_similarity = similarities[max_idx]
        
        if max_similarity >= self.similarity_threshold:
            return self._keys[max_idx], float(max_similarity)
        
        return None
    
    def get(self, query: str) -> Optional[Tuple[str, float, str]]:
        """
        获取缓存
        
        Returns:
            Tuple of (matched_query, similarity, response) or None
        """
        self._stats['total_requests'] += 1
        
        # 生成查询键
        query_key = self._generate_key(query)
        
        # 检查精确匹配
        if query_key in self._cache:
            entry = self._cache[query_key]
            if not self._is_expired(entry):
                self._update_access(entry)
                self._stats['cache_hits'] += 1
                self._stats['exact_hits'] += 1
                return entry.query, 1.0, entry.response
            else:
                # 过期删除
                self._remove_entry(query_key)
        
        # 计算查询向量
        query_embedding = self._compute_embedding(query)
        
        # 查找语义相似
        similar = self._find_similar(query_embedding)
        if similar:
            key, similarity = similar
            entry = self._cache[key]
            if not self._is_expired(entry):
                self._update_access(entry)
                self._stats['cache_hits'] += 1
                self._stats['semantic_hits'] += 1
                return entry.query, similarity, entry.response
            else:
                self._remove_entry(key)
        
        self._stats['cache_misses'] += 1
        return None
    
    def set(
        self, 
        query: str, 
        response: str, 
        ttl: int = 3600
    ) -> None:
        """设置缓存"""
        # 检查容量
        if len(self._cache) >= self.max_entries:
            self._evict_oldest()
        
        # 生成键和向量
        key = self._generate_key(query)
        embedding = self._compute_embedding(query)
        
        # 创建条目
        entry = CacheEntry(
            query=query,
            response=response,
            embedding=embedding,
            timestamp=time.time(),
            ttl=ttl
        )
        
        # 存储
        self._cache[key] = entry
        
        # 更新索引
        if key in self._keys:
            idx = self._keys.index(key)
            self._embeddings[idx] = embedding
        else:
            self._keys.append(key)
            self._embeddings.append(embedding)
    
    def put(
        self, 
        query: str, 
        response: str, 
        ttl: int = 3600
    ) -> None:
        """设置缓存（别名，兼容 put 调用）"""
        self.set(query, response, ttl)
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查是否过期"""
        return time.time() - entry.timestamp > entry.ttl
    
    def _update_access(self, entry: CacheEntry) -> None:
        """更新访问信息"""
        entry.hit_count += 1
        entry.access_times.append(time.time())
        # 只保留最近100次访问时间
        entry.access_times = entry.access_times[-100:]
    
    def _remove_entry(self, key: str) -> None:
        """删除条目"""
        if key in self._cache:
            del self._cache[key]
            if key in self._keys:
                idx = self._keys.index(key)
                self._keys.pop(idx)
                self._embeddings.pop(idx)
    
    def _evict_oldest(self) -> None:
        """淘汰最旧的条目"""
        if not self._cache:
            return
        
        # 找到最久未访问的
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].access_times[-1] 
            if self._cache[k].access_times 
            else self._cache[k].timestamp
        )
        self._remove_entry(oldest_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats['total_requests']
        hit_rate = self._stats['cache_hits'] / total if total > 0 else 0
        
        hot_queries = sorted(
            [{'query': e.query, 'hits': e.hit_count} for e in self._cache.values() if e.hit_count > 0],
            key=lambda x: x['hits'],
            reverse=True
        )[:10]
        
        return {
            **self._stats,
            'hit_rate': hit_rate,
            'cache_size': len(self._cache),
            'max_size': self.max_entries,
            'hot_queries': hot_queries
        }
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._embeddings.clear()
        self._keys.clear()
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'semantic_hits': 0,
            'exact_hits': 0
        }
    
    def cleanup_expired(self) -> int:
        """清理过期条目，返回清理数量"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if self._is_expired(entry)
        ]
        for key in expired_keys:
            self._remove_entry(key)
        return len(expired_keys)
