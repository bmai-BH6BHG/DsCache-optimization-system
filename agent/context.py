"""
上下文管理器 - 管理对话历史和代码上下文
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import time
import hashlib


@dataclass
class ConversationTurn:
    """对话回合"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeContext:
    """代码上下文"""
    file_path: str
    language: str
    content: str
    cursor_position: Optional[int] = None
    selected_text: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)


class ContextManager:
    """上下文管理器"""
    
    def __init__(
        self,
        max_history: int = 10,
        context_window: int = 4096,
        relevance_threshold: float = 0.7
    ):
        self.max_history = max_history
        self.context_window = context_window
        self.relevance_threshold = relevance_threshold
        
        # 对话历史
        self.conversation_history: deque = deque(maxlen=max_history)
        
        # 代码上下文
        self.current_code_context: Optional[CodeContext] = None
        
        # 上下文缓存
        self._context_cache: Dict[str, Any] = {}
        
        # 统计
        self.stats = {
            'context_hits': 0,
            'context_misses': 0
        }
    
    def add_turn(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """添加对话回合"""
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        self.conversation_history.append(turn)
    
    def get_relevant_context(
        self, 
        query: str, 
        max_tokens: Optional[int] = None
    ) -> str:
        """
        获取与查询相关的上下文
        
        Args:
            query: 当前查询
            max_tokens: 最大 token 数
        
        Returns:
            格式化的上下文字符串
        """
        if max_tokens is None:
            max_tokens = self.context_window
        
        context_parts = []
        current_tokens = 0
        
        # 1. 添加代码上下文
        if self.current_code_context:
            code_ctx = self._format_code_context(self.current_code_context)
            code_tokens = len(code_ctx) // 4  # 粗略估算
            
            if current_tokens + code_tokens < max_tokens:
                context_parts.append(code_ctx)
                current_tokens += code_tokens
        
        # 2. 添加相关对话历史
        relevant_history = self._get_relevant_history(query)
        
        for turn in reversed(relevant_history):
            turn_text = f"{turn.role}: {turn.content}\n"
            turn_tokens = len(turn_text) // 4
            
            if current_tokens + turn_tokens > max_tokens:
                break
            
            context_parts.insert(0, turn_text)
            current_tokens += turn_tokens
        
        return '\n'.join(context_parts)
    
    def _format_code_context(self, ctx: CodeContext) -> str:
        """格式化代码上下文"""
        parts = []
        
        if ctx.file_path:
            parts.append(f"File: {ctx.file_path}")
        
        if ctx.language:
            parts.append(f"Language: {ctx.language}")
        
        if ctx.imports:
            parts.append(f"Imports: {', '.join(ctx.imports[:5])}")
        
        if ctx.selected_text:
            parts.append(f"Selected code:\n```\n{ctx.selected_text}\n```")
        elif ctx.content:
            # 只取部分内容
            preview = ctx.content[:500] + "..." if len(ctx.content) > 500 else ctx.content
            parts.append(f"Current file content:\n```\n{preview}\n```")
        
        return '\n'.join(parts)
    
    def _get_relevant_history(self, query: str) -> List[ConversationTurn]:
        """获取相关的对话历史"""
        if not self.conversation_history:
            return []
        
        # 简单的相关性判断：检查关键词重叠
        query_words = set(query.lower().split())
        
        scored_history = []
        for turn in self.conversation_history:
            turn_words = set(turn.content.lower().split())
            overlap = len(query_words & turn_words)
            score = overlap / max(len(query_words), 1)
            
            if score >= self.relevance_threshold:
                scored_history.append((turn, score))
        
        # 按相关性和时间排序
        scored_history.sort(key=lambda x: (x[1], x[0].timestamp), reverse=True)
        
        return [turn for turn, _ in scored_history[:5]]
    
    def update_code_context(self, **kwargs) -> None:
        """更新代码上下文"""
        if self.current_code_context is None:
            self.current_code_context = CodeContext(**kwargs)
        else:
            for key, value in kwargs.items():
                if hasattr(self.current_code_context, key):
                    setattr(self.current_code_context, key, value)
    
    def get_context_hash(self) -> str:
        """获取当前上下文的哈希值"""
        context_str = self._serialize_context()
        return hashlib.md5(context_str.encode()).hexdigest()
    
    def _serialize_context(self) -> str:
        """序列化上下文"""
        parts = []
        
        # 序列化对话历史
        for turn in self.conversation_history:
            parts.append(f"{turn.role}:{turn.content}")
        
        # 序列化代码上下文
        if self.current_code_context:
            ctx = self.current_code_context
            parts.append(f"file:{ctx.file_path}")
            parts.append(f"lang:{ctx.language}")
        
        return '|'.join(parts)
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history.clear()
    
    def clear_code_context(self) -> None:
        """清空代码上下文"""
        self.current_code_context = None
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'history_size': len(self.conversation_history),
            'has_code_context': self.current_code_context is not None
        }
