"""
Cache module for DeepSeek Cache Optimizer
"""

from .semantic import SemanticCache
from .multi_level import MultiLevelCache
from .adaptive_ttl import AdaptiveTTLManager

__all__ = ['SemanticCache', 'MultiLevelCache', 'AdaptiveTTLManager']
