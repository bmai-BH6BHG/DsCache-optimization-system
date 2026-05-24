"""
轻量级记忆系统 - 灵感来自 Mem0
支持长期记忆、语义搜索、知识库管理
"""
import os
import json
import time
import hashlib
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional


class MemorySystem:
    """轻量级记忆系统，支持语义搜索和知识库"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.memory_db = os.path.join(data_dir, 'memory.db')
        self.knowledge_db = os.path.join(data_dir, 'knowledge.db')
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        # 记忆数据库
        c = sqlite3.connect(self.memory_db)
        c.execute('''CREATE TABLE IF NOT EXISTS memories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            memory_type TEXT DEFAULT 'episodic',
            content TEXT NOT NULL,
            embedding_hash TEXT,
            metadata TEXT,
            created_at REAL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 1,
            importance REAL DEFAULT 0.5
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON memories(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)')
        c.commit()
        c.close()
        
        # 知识库数据库
        k = sqlite3.connect(self.knowledge_db)
        k.execute('''CREATE TABLE IF NOT EXISTS knowledge(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT DEFAULT 'general',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            source TEXT,
            created_at REAL,
            updated_at REAL,
            access_count INTEGER DEFAULT 1
        )''')
        k.execute('CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category)')
        k.execute('CREATE INDEX IF NOT EXISTS idx_tags ON knowledge(tags)')
        k.commit()
        k.close()
    
    def add_memory(self, content: str, user_id: str = 'default', 
                   memory_type: str = 'episodic', metadata: Dict = None,
                   importance: float = 0.5) -> int:
        """添加记忆
        
        memory_type: episodic(事件), semantic(知识), procedural(流程), preference(偏好)
        """
        c = sqlite3.connect(self.memory_db)
        embedding_hash = hashlib.md5(content.lower().encode()).hexdigest()
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else '{}'
        now = time.time()
        
        cursor = c.execute('''INSERT INTO memories 
            (user_id, memory_type, content, embedding_hash, metadata, created_at, last_accessed, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, memory_type, content, embedding_hash, metadata_json, now, now, importance))
        memory_id = cursor.lastrowid
        c.commit()
        c.close()
        return memory_id
    
    def search_memories(self, query: str, user_id: str = 'default',
                        limit: int = 5, memory_type: str = None) -> List[Dict]:
        """搜索记忆（基于文本相似度）"""
        c = sqlite3.connect(self.memory_db)
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # 获取所有相关记忆
        if memory_type:
            rows = c.execute('''SELECT id, user_id, memory_type, content, metadata, 
                created_at, last_accessed, access_count, importance 
                FROM memories WHERE user_id = ? AND memory_type = ?
                ORDER BY importance DESC, last_accessed DESC LIMIT 100''',
                (user_id, memory_type)).fetchall()
        else:
            rows = c.execute('''SELECT id, user_id, memory_type, content, metadata,
                created_at, last_accessed, access_count, importance
                FROM memories WHERE user_id = ?
                ORDER BY importance DESC, last_accessed DESC LIMIT 100''',
                (user_id,)).fetchall()
        c.close()
        
        # 计算相似度并排序
        results = []
        for row in rows:
            content_lower = row[3].lower()
            content_words = set(content_lower.split())
            
            # Jaccard 相似度
            intersection = len(query_words & content_words)
            union = len(query_words | content_words)
            similarity = intersection / union if union > 0 else 0
            
            # 包含匹配加分
            if query_lower in content_lower:
                similarity += 0.3
            
            if similarity > 0.1:
                results.append({
                    'id': row[0],
                    'user_id': row[1],
                    'memory_type': row[2],
                    'content': row[3],
                    'metadata': json.loads(row[4]) if row[4] else {},
                    'created_at': row[5],
                    'last_accessed': row[6],
                    'access_count': row[7],
                    'importance': row[8],
                    'similarity': similarity
                })
        
        # 按相似度排序并返回 top N
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    
    def get_all_memories(self, user_id: str = 'default', 
                         memory_type: str = None, limit: int = 100) -> List[Dict]:
        """获取所有记忆"""
        c = sqlite3.connect(self.memory_db)
        if memory_type:
            rows = c.execute('''SELECT id, user_id, memory_type, content, metadata,
                created_at, last_accessed, access_count, importance
                FROM memories WHERE user_id = ? AND memory_type = ?
                ORDER BY created_at DESC LIMIT ?''',
                (user_id, memory_type, limit)).fetchall()
        else:
            rows = c.execute('''SELECT id, user_id, memory_type, content, metadata,
                created_at, last_accessed, access_count, importance
                FROM memories WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?''',
                (user_id, limit)).fetchall()
        c.close()
        
        return [{
            'id': r[0], 'user_id': r[1], 'memory_type': r[2],
            'content': r[3], 'metadata': json.loads(r[4]) if r[4] else {},
            'created_at': r[5], 'last_accessed': r[6],
            'access_count': r[7], 'importance': r[8]
        } for r in rows]
    
    def update_memory_access(self, memory_id: int):
        """更新记忆访问时间和次数"""
        c = sqlite3.connect(self.memory_db)
        c.execute('''UPDATE memories SET last_accessed = ?, access_count = access_count + 1
            WHERE id = ?''', (time.time(), memory_id))
        c.commit()
        c.close()
    
    def delete_memory(self, memory_id: int):
        """删除记忆"""
        c = sqlite3.connect(self.memory_db)
        c.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
        c.commit()
        c.close()
    
    def clear_memories(self, user_id: str = None, memory_type: str = None):
        """清空记忆"""
        c = sqlite3.connect(self.memory_db)
        if user_id and memory_type:
            c.execute('DELETE FROM memories WHERE user_id = ? AND memory_type = ?',
                     (user_id, memory_type))
        elif user_id:
            c.execute('DELETE FROM memories WHERE user_id = ?', (user_id,))
        elif memory_type:
            c.execute('DELETE FROM memories WHERE memory_type = ?', (memory_type,))
        else:
            c.execute('DELETE FROM memories')
        c.commit()
        c.close()
    
    # ===== 知识库功能 =====
    
    def add_knowledge(self, title: str, content: str, category: str = 'general',
                      tags: List[str] = None, source: str = None) -> int:
        """添加知识"""
        k = sqlite3.connect(self.knowledge_db)
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else '[]'
        now = time.time()
        cursor = k.execute('''INSERT INTO knowledge
            (category, title, content, tags, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (category, title, content, tags_json, source, now, now))
        knowledge_id = cursor.lastrowid
        k.commit()
        k.close()
        return knowledge_id
    
    def search_knowledge(self, query: str, category: str = None, limit: int = 5) -> List[Dict]:
        """搜索知识"""
        k = sqlite3.connect(self.knowledge_db)
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        if category:
            rows = k.execute('''SELECT id, category, title, content, tags, source,
                created_at, updated_at, access_count
                FROM knowledge WHERE category = ?
                ORDER BY access_count DESC LIMIT 100''', (category,)).fetchall()
        else:
            rows = k.execute('''SELECT id, category, title, content, tags, source,
                created_at, updated_at, access_count
                FROM knowledge ORDER BY access_count DESC LIMIT 100''').fetchall()
        k.close()
        
        results = []
        for row in rows:
            title_lower = row[2].lower()
            content_lower = row[3].lower()
            combined = title_lower + ' ' + content_lower
            combined_words = set(combined.split())
            
            intersection = len(query_words & combined_words)
            union = len(query_words | combined_words)
            similarity = intersection / union if union > 0 else 0
            
            if query_lower in combined:
                similarity += 0.3
            
            if similarity > 0.1:
                results.append({
                    'id': row[0], 'category': row[1], 'title': row[2],
                    'content': row[3], 'tags': json.loads(row[4]) if row[4] else [],
                    'source': row[5], 'created_at': row[6], 'updated_at': row[7],
                    'access_count': row[8], 'similarity': similarity
                })
        
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    
    def get_all_knowledge(self, category: str = None, limit: int = 100) -> List[Dict]:
        """获取所有知识"""
        k = sqlite3.connect(self.knowledge_db)
        if category:
            rows = k.execute('''SELECT id, category, title, content, tags, source,
                created_at, updated_at, access_count
                FROM knowledge WHERE category = ?
                ORDER BY created_at DESC LIMIT ?''', (category, limit)).fetchall()
        else:
            rows = k.execute('''SELECT id, category, title, content, tags, source,
                created_at, updated_at, access_count
                FROM knowledge ORDER BY created_at DESC LIMIT ?''', (limit,)).fetchall()
        k.close()
        
        return [{
            'id': r[0], 'category': r[1], 'title': r[2],
            'content': r[3], 'tags': json.loads(r[4]) if r[4] else [],
            'source': r[5], 'created_at': r[6], 'updated_at': r[7],
            'access_count': r[8]
        } for r in rows]
    
    def update_knowledge(self, knowledge_id: int, title: str = None, 
                        content: str = None, tags: List[str] = None):
        """更新知识"""
        k = sqlite3.connect(self.knowledge_db)
        now = time.time()
        
        if title:
            k.execute('UPDATE knowledge SET title = ?, updated_at = ? WHERE id = ?',
                     (title, now, knowledge_id))
        if content:
            k.execute('UPDATE knowledge SET content = ?, updated_at = ? WHERE id = ?',
                     (content, now, knowledge_id))
        if tags:
            tags_json = json.dumps(tags, ensure_ascii=False)
            k.execute('UPDATE knowledge SET tags = ?, updated_at = ? WHERE id = ?',
                     (tags_json, now, knowledge_id))
        
        k.commit()
        k.close()
    
    def delete_knowledge(self, knowledge_id: int):
        """删除知识"""
        k = sqlite3.connect(self.knowledge_db)
        k.execute('DELETE FROM knowledge WHERE id = ?', (knowledge_id,))
        k.commit()
        k.close()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        c = sqlite3.connect(self.memory_db)
        memory_count = c.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
        memory_by_type = c.execute('''SELECT memory_type, COUNT(*) 
            FROM memories GROUP BY memory_type''').fetchall()
        c.close()
        
        k = sqlite3.connect(self.knowledge_db)
        knowledge_count = k.execute('SELECT COUNT(*) FROM knowledge').fetchone()[0]
        knowledge_by_category = k.execute('''SELECT category, COUNT(*)
            FROM knowledge GROUP BY category''').fetchall()
        k.close()
        
        return {
            'memory_count': memory_count,
            'memory_by_type': dict(memory_by_type),
            'knowledge_count': knowledge_count,
            'knowledge_by_category': dict(knowledge_by_category)
        }
