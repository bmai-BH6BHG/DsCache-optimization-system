"""
多级缓存实现 - L1(内存) -> L2(SQLite) -> L3(文件)
"""

import json
import os
import pickle
import sqlite3
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from threading import Lock
import asyncio
import aiofiles


@dataclass
class CacheMetadata:
    """缓存元数据"""
    key: str
    level: int
    created_at: float
    expires_at: float
    size: int
    hit_count: int = 0
    last_accessed: float = 0


class L1MemoryCache:
    """L1 内存缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, Any] = {}
        self._metadata: Dict[str, CacheMetadata] = {}
        self._lock = Lock()
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            meta = self._metadata[key]
            if time.time() > meta.expires_at:
                self._remove(key)
                self._stats['misses'] += 1
                return None
            
            # 更新访问信息
            meta.hit_count += 1
            meta.last_accessed = time.time()
            self._stats['hits'] += 1
            
            return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        if ttl is None:
            ttl = self.ttl
        
        with self._lock:
            # 检查容量
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            # 计算大小（近似值）
            size = len(pickle.dumps(value))
            
            self._cache[key] = value
            self._metadata[key] = CacheMetadata(
                key=key,
                level=1,
                created_at=time.time(),
                expires_at=time.time() + ttl,
                size=size
            )
    
    def _remove(self, key: str) -> None:
        """删除缓存"""
        self._cache.pop(key, None)
        self._metadata.pop(key, None)
    
    def _evict_lru(self) -> None:
        """LRU 淘汰"""
        if not self._metadata:
            return
        
        # 找到最久未访问的
        lru_key = min(
            self._metadata.keys(),
            key=lambda k: self._metadata[k].last_accessed 
            if self._metadata[k].last_accessed > 0 
            else self._metadata[k].created_at
        )
        self._remove(lru_key)
        self._stats['evictions'] += 1
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            'size': len(self._cache),
            'max_size': self.max_size,
            'hit_rate': self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])
            if (self._stats['hits'] + self._stats['misses']) > 0 else 0
        }


class L2SQLiteCache:
    """L2 SQLite 缓存"""
    
    def __init__(self, db_path: str = "H:\\deepgui\\deepseek-cache-optimizer\\data\\cache_l2.db", max_size: int = 10000, ttl: int = 3600):
        self.db_path = db_path
        self.max_size = max_size
        self.ttl = ttl
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}
        
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化数据库
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                created_at REAL,
                expires_at REAL,
                size INTEGER,
                hit_count INTEGER DEFAULT 0,
                last_accessed REAL DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)
        ''')
        
        conn.commit()
        conn.close()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?",
            (key,)
        )
        result = cursor.fetchone()
        
        if not result:
            self._stats['misses'] += 1
            conn.close()
            return None
        
        value_blob, expires_at = result
        
        if time.time() > expires_at:
            cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            self._stats['misses'] += 1
            conn.close()
            return None
        
        # 更新访问信息
        cursor.execute(
            "UPDATE cache SET hit_count = hit_count + 1, last_accessed = ? WHERE key = ?",
            (time.time(), key)
        )
        conn.commit()
        conn.close()
        
        self._stats['hits'] += 1
        return pickle.loads(value_blob)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        if ttl is None:
            ttl = self.ttl
        
        # 序列化值
        value_blob = pickle.dumps(value)
        size = len(value_blob)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查容量
        cursor.execute("SELECT COUNT(*) FROM cache")
        count = cursor.fetchone()[0]
        
        if count >= self.max_size:
            # 淘汰最旧的
            cursor.execute('''
                DELETE FROM cache WHERE key = (
                    SELECT key FROM cache 
                    ORDER BY last_accessed ASC, created_at ASC 
                    LIMIT 1
                )
            ''')
            self._stats['evictions'] += 1
        
        # 插入或更新
        cursor.execute('''
            INSERT OR REPLACE INTO cache 
            (key, value, created_at, expires_at, size)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            key,
            value_blob,
            time.time(),
            time.time() + ttl,
            size
        ))
        
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """获取统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cache")
        size = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            **self._stats,
            'size': size,
            'max_size': self.max_size,
            'hit_rate': self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])
            if (self._stats['hits'] + self._stats['misses']) > 0 else 0
        }


class L3FileCache:
    """L3 文件缓存"""
    
    def __init__(self, storage_path: str = "./cache_l3", max_size: int = 100000, ttl: int = 86400):
        self.storage_path = storage_path
        self.max_size = max_size
        self.ttl = ttl
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}
        
        # 确保目录存在
        os.makedirs(storage_path, exist_ok=True)
    
    def _get_file_path(self, key: str) -> str:
        """获取文件路径"""
        # 使用子目录分散文件
        subdir = key[:2]
        dir_path = os.path.join(self.storage_path, subdir)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"{key}.cache")
    
    def _get_meta_path(self, key: str) -> str:
        """获取元数据文件路径"""
        return self._get_file_path(key) + ".meta"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        file_path = self._get_file_path(key)
        meta_path = self._get_meta_path(key)
        
        if not os.path.exists(file_path):
            self._stats['misses'] += 1
            return None
        
        # 读取元数据
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            if time.time() > meta['expires_at']:
                os.remove(file_path)
                os.remove(meta_path)
                self._stats['misses'] += 1
                return None
            
            # 读取值
            with open(file_path, 'rb') as f:
                value = pickle.load(f)
            
            # 更新元数据
            meta['hit_count'] += 1
            meta['last_accessed'] = time.time()
            with open(meta_path, 'w') as f:
                json.dump(meta, f)
            
            self._stats['hits'] += 1
            return value
            
        except Exception:
            self._stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        if ttl is None:
            ttl = self.ttl
        
        # 检查容量
        self._check_capacity()
        
        file_path = self._get_file_path(key)
        meta_path = self._get_meta_path(key)
        
        # 保存值
        with open(file_path, 'wb') as f:
            pickle.dump(value, f)
        
        # 保存元数据
        meta = {
            'key': key,
            'created_at': time.time(),
            'expires_at': time.time() + ttl,
            'size': os.path.getsize(file_path),
            'hit_count': 0,
            'last_accessed': 0
        }
        
        with open(meta_path, 'w') as f:
            json.dump(meta, f)
    
    def _check_capacity(self) -> None:
        """检查容量并淘汰"""
        cache_files = []
        total_size = 0
        
        for root, dirs, files in os.walk(self.storage_path):
            for file in files:
                if file.endswith('.cache'):
                    path = os.path.join(root, file)
                    stat = os.stat(path)
                    cache_files.append({
                        'path': path,
                        'meta_path': path + '.meta',
                        'atime': stat.st_atime,
                        'size': stat.st_size
                    })
                    total_size += 1
        
        if total_size >= self.max_size:
            # 按访问时间排序，删除最旧的
            cache_files.sort(key=lambda x: x['atime'])
            to_remove = cache_files[:total_size - self.max_size + 1]
            
            for item in to_remove:
                try:
                    os.remove(item['path'])
                    if os.path.exists(item['meta_path']):
                        os.remove(item['meta_path'])
                    self._stats['evictions'] += 1
                except Exception:
                    pass
    
    def get_stats(self) -> Dict:
        """获取统计"""
        count = 0
        for root, dirs, files in os.walk(self.storage_path):
            count += sum(1 for f in files if f.endswith('.cache'))
        
        return {
            **self._stats,
            'size': count,
            'max_size': self.max_size,
            'hit_rate': self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])
            if (self._stats['hits'] + self._stats['misses']) > 0 else 0
        }


class MultiLevelCache:
    """多级缓存管理器"""
    
    def __init__(
        self,
        l1_config: Optional[Dict] = None,
        l2_config: Optional[Dict] = None,
        l3_config: Optional[Dict] = None
    ):
        # 默认配置
        l1_default = {'max_size': 1000, 'ttl': 300}
        l2_default = {'db_path': 'H:\\deepgui\\deepseek-cache-optimizer\\data\\cache_l2.db', 'max_size': 10000, 'ttl': 3600}
        l3_default = {'storage_path': 'H:\\deepgui\\deepseek-cache-optimizer\\data\\cache_l3', 'max_size': 100000, 'ttl': 86400}
        
        # 初始化各级缓存
        self.l1 = L1MemoryCache(**{**l1_default, **(l1_config or {})})
        self.l2 = L2SQLiteCache(**{**l2_default, **(l2_config or {})})
        self.l3 = L3FileCache(**{**l3_default, **(l3_config or {})})
        
        self._stats = {
            'total_requests': 0,
            'l1_hits': 0,
            'l2_hits': 0,
            'l3_hits': 0,
            'misses': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存（按 L1 -> L2 -> L3 顺序）"""
        self._stats['total_requests'] += 1
        
        # 尝试 L1
        value = self.l1.get(key)
        if value is not None:
            self._stats['l1_hits'] += 1
            return value
        
        # 尝试 L2
        value = self.l2.get(key)
        if value is not None:
            self._stats['l2_hits'] += 1
            # 提升到 L1
            self.l1.set(key, value)
            return value
        
        # 尝试 L3
        value = self.l3.get(key)
        if value is not None:
            self._stats['l3_hits'] += 1
            # 提升到 L2 和 L1
            self.l2.set(key, value)
            self.l1.set(key, value)
            return value
        
        self._stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存（写入所有级别）"""
        self.l1.set(key, value, ttl)
        self.l2.set(key, value, ttl)
        self.l3.set(key, value, ttl)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_hits = self._stats['l1_hits'] + self._stats['l2_hits'] + self._stats['l3_hits']
        total = self._stats['total_requests']
        
        return {
            **self._stats,
            'total_hits': total_hits,
            'hit_rate': total_hits / total if total > 0 else 0,
            'l1': self.l1.get_stats(),
            'l2': self.l2.get_stats(),
            'l3': self.l3.get_stats()
        }
