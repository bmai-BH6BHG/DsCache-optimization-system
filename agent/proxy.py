"""
智能体代理 - 请求拦截和改写
"""

import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import time


@dataclass
class ProcessedRequest:
    """处理后的请求"""
    original_query: str
    normalized_query: str
    cache_key: str
    context_hash: str
    should_cache: bool
    priority: int
    metadata: Dict[str, Any]


class AgentProxy:
    """智能体代理 - 拦截和处理 DeepSeek 请求"""
    
    def __init__(self):
        # 代码模式识别
        self.code_patterns = {
            'function_def': r'(?:def|function|func)\s+\w+',
            'class_def': r'(?:class)\s+\w+',
            'import_stmt': r'(?:import|from|using|require)',
            'variable_assign': r'\w+\s*=\s*',
            'comment': r'(?:#|//|/\*|<!--)',
        }
        
        # 对话模式识别
        self.conversation_patterns = {
            'question': r'[？?]\s*$',
            'greeting': r'^(?:你好|您好|hi|hello|hey)',
            'help_request': r'(?:帮助|help|assist|support)',
            'explanation': r'(?:解释|explain|what is|什么是)',
        }
        
        # 缓存策略配置
        self.cache_policies = {
            'code_generation': {'should_cache': True, 'priority': 1, 'ttl_multiplier': 2.0},
            'code_explanation': {'should_cache': True, 'priority': 2, 'ttl_multiplier': 1.5},
            'general_qa': {'should_cache': True, 'priority': 3, 'ttl_multiplier': 1.0},
            'conversation': {'should_cache': False, 'priority': 4, 'ttl_multiplier': 0.5},
            'debugging': {'should_cache': True, 'priority': 2, 'ttl_multiplier': 1.2},
        }
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'cached_requests': 0,
            'normalized_requests': 0
        }
    
    def process_request(
        self, 
        query: str, 
        context: Optional[str] = None,
        request_type: Optional[str] = None
    ) -> ProcessedRequest:
        """
        处理请求 - 归一化、分类、生成缓存键
        
        Args:
            query: 原始查询
            context: 上下文信息
            request_type: 请求类型（如果已知）
        
        Returns:
            ProcessedRequest: 处理后的请求
        """
        self.stats['total_requests'] += 1
        
        # 1. 归一化查询
        normalized = self._normalize_query(query)
        
        # 2. 检测请求类型
        if request_type is None:
            request_type = self._detect_request_type(normalized)
        
        # 3. 获取缓存策略
        policy = self.cache_policies.get(request_type, self.cache_policies['general_qa'])
        
        # 4. 生成缓存键
        cache_key = self._generate_cache_key(normalized, context)
        
        # 5. 生成上下文哈希
        context_hash = self._hash_context(context) if context else ""
        
        # 6. 构建元数据
        metadata = {
            'request_type': request_type,
            'query_length': len(query),
            'normalized_length': len(normalized),
            'has_code': self._contains_code(normalized),
            'has_context': context is not None,
            'timestamp': time.time()
        }
        
        # 7. 决定是否缓存
        should_cache = policy['should_cache'] and self._should_cache_request(normalized, request_type)
        
        if should_cache:
            self.stats['cached_requests'] += 1
        
        return ProcessedRequest(
            original_query=query,
            normalized_query=normalized,
            cache_key=cache_key,
            context_hash=context_hash,
            should_cache=should_cache,
            priority=policy['priority'],
            metadata=metadata
        )
    
    def _normalize_query(self, query: str) -> str:
        """归一化查询以提高缓存命中率"""
        original = query
        
        # 1. 去除首尾空白
        query = query.strip()
        
        # 2. 统一空白字符
        query = re.sub(r'\s+', ' ', query)
        
        # 3. 转换为小写（保持代码部分不变）
        # 分离代码和非代码部分
        code_blocks = re.findall(r'```[\s\S]*?```|`[^`]*`', query)
        non_code_parts = re.split(r'```[\s\S]*?```|`[^`]*`', query)
        
        normalized_parts = []
        for i, part in enumerate(non_code_parts):
            # 非代码部分转小写
            normalized_parts.append(part.lower())
            # 添加代码块（保持原样）
            if i < len(code_blocks):
                normalized_parts.append(code_blocks[i])
        
        query = ''.join(normalized_parts)
        
        # 4. 标准化标点符号
        query = re.sub(r'[，,]', ', ', query)
        query = re.sub(r'[。]', '. ', query)
        query = re.sub(r'[？?]', '?', query)
        query = re.sub(r'[！!]', '!', query)
        
        # 5. 去除多余空格
        query = re.sub(r'\s+', ' ', query).strip()
        
        if query != original:
            self.stats['normalized_requests'] += 1
        
        return query
    
    def _detect_request_type(self, query: str) -> str:
        """检测请求类型"""
        query_lower = query.lower()
        
        # 检查代码生成模式
        code_indicators = [
            '写', '编写', '生成', 'create', 'write', 'generate', 'implement',
            'function', 'class', 'def ', '代码', 'code'
        ]
        if any(ind in query_lower for ind in code_indicators):
            if self._contains_code(query):
                return 'code_explanation'
            return 'code_generation'
        
        # 检查调试模式
        debug_indicators = [
            'bug', 'error', 'debug', 'fix', 'issue', 'problem', '报错',
            '错误', '调试', '修复'
        ]
        if any(ind in query_lower for ind in debug_indicators):
            return 'debugging'
        
        # 检查对话模式
        conv_indicators = [
            '你好', '您好', '谢谢', 'help', 'assist', 'explain'
        ]
        if any(ind in query_lower for ind in conv_indicators):
            return 'conversation'
        
        return 'general_qa'
    
    def _contains_code(self, query: str) -> bool:
        """检查查询是否包含代码"""
        # 检查代码块
        if '```' in query or '`' in query:
            return True
        
        # 检查代码模式
        for pattern in self.code_patterns.values():
            if re.search(pattern, query, re.IGNORECASE):
                return True
        
        return False
    
    def _generate_cache_key(self, normalized_query: str, context: Optional[str]) -> str:
        """生成缓存键"""
        # 基础键
        key_content = normalized_query
        
        # 如果有上下文，加入上下文哈希
        if context:
            context_hash = hashlib.md5(context.encode()).hexdigest()[:8]
            key_content = f"{key_content}|ctx:{context_hash}"
        
        return hashlib.md5(key_content.encode()).hexdigest()
    
    def _hash_context(self, context: str) -> str:
        """生成上下文哈希"""
        return hashlib.md5(context.encode()).hexdigest()
    
    def _should_cache_request(self, query: str, request_type: str) -> bool:
        """决定是否应该缓存此请求"""
        # 太短的不缓存
        if len(query) < 10:
            return False
        
        # 包含敏感信息的不缓存
        sensitive_patterns = [
            r'password\s*=',
            r'secret\s*=',
            r'api[_-]?key',
            r'token\s*=',
            r'密码',
            r'密钥'
        ]
        for pattern in sensitive_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return False
        
        # 高度个性化的不缓存
        personalized_indicators = [
            r'我的', r'my ', r'我的文件', r'我的项目',
            r'这个文件', r'这段代码', r'当前'
        ]
        personalized_count = sum(
            1 for ind in personalized_indicators 
            if ind in query.lower()
        )
        if personalized_count > 2:
            return False
        
        return True
    
    def rewrite_for_cache(
        self, 
        query: str, 
        similarity_threshold: float = 0.85
    ) -> List[str]:
        """
        改写查询以匹配可能的缓存
        
        Returns:
            改写后的查询列表，按优先级排序
        """
        variations = [query]
        
        # 1. 去除礼貌用语
        polite_patterns = [
            r'^(?:请问|请|麻烦|能否|可以).*?[，,]?',
            r'(?:谢谢|感谢).*?$',
            r'^(?:hi|hello|hey)\s+',
        ]
        
        for pattern in polite_patterns:
            cleaned = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
            if cleaned and cleaned != query:
                variations.append(cleaned)
        
        # 2. 提取核心问题
        core_question = self._extract_core_question(query)
        if core_question and core_question not in variations:
            variations.append(core_question)
        
        # 3. 标准化编程语言名称
        lang_mapping = {
            'python': ['py', 'python3'],
            'javascript': ['js', 'node', 'nodejs'],
            'typescript': ['ts'],
            'java': ['java'],
            'cpp': ['c++', 'cplusplus'],
        }
        
        for standard, aliases in lang_mapping.items():
            for alias in aliases:
                if alias in query.lower():
                    standardized = re.sub(
                        rf'\b{alias}\b', 
                        standard, 
                        query, 
                        flags=re.IGNORECASE
                    )
                    if standardized not in variations:
                        variations.append(standardized)
        
        return variations
    
    def _extract_core_question(self, query: str) -> Optional[str]:
        """提取核心问题"""
        # 移除礼貌用语
        query = re.sub(r'^(?:请问|请|麻烦|能否|可以)', '', query)
        query = re.sub(r'(?:谢谢|感谢).*?$', '', query)
        
        # 提取问句
        question_match = re.search(r'[^.!?]*[？?]', query)
        if question_match:
            return question_match.group(0).strip()
        
        # 提取命令式语句
        command_match = re.search(r'(?:如何|怎么|怎样|what|how|why).*', query, re.IGNORECASE)
        if command_match:
            return command_match.group(0).strip()
        
        return None
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'cache_rate': (
                self.stats['cached_requests'] / self.stats['total_requests']
                if self.stats['total_requests'] > 0 else 0
            )
        }
