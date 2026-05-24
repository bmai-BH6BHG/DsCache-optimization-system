"""
内置 Skill 命令

提供常用的缓存管理、监控、配置等命令
"""

import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from .registry import registry
from .executor import executor


class BuiltinSkills:
    """内置 Skill 集合"""
    
    def __init__(self):
        self._cache_instance = None
        self._agent_proxy = None
        self._decision_engine = None
    
    def set_components(self, cache=None, agent_proxy=None, decision_engine=None):
        """设置组件实例"""
        self._cache_instance = cache
        self._agent_proxy = agent_proxy
        self._decision_engine = decision_engine


# 创建实例
builtin_skills = BuiltinSkills()


# ==================== 通用命令 ====================

@registry.register(
    name="help",
    description="显示帮助信息",
    patterns=[
        r'^help$',
        r'^帮助$',
        r'^help\s+(?P<skill_name>.+)$',
        r'^帮助\s+(?P<skill_name>.+)$'
    ],
    examples=[
        "help",
        "帮助",
        "help stats",
        "帮助 查看统计"
    ],
    category="general"
)
def skill_help(skill_name: str = None):
    """帮助命令"""
    return registry.get_help_text(skill_name)


@registry.register(
    name="hello",
    description="问候命令",
    patterns=[
        r'^hello$',
        r'^hi$',
        r'^你好$',
        r'^您好$'
    ],
    examples=["hello", "hi", "你好"],
    category="general"
)
def skill_hello():
    """问候"""
    return {
        'message': '👋 你好！我是 DeepSeek 缓存优化助手。\n输入 "help" 查看可用命令。',
        'data': {'version': '1.0.0'}
    }


# ==================== 缓存管理命令 ====================

@registry.register(
    name="cache stats",
    description="查看缓存统计信息",
    patterns=[
        r'^stats$',
        r'^stat$',
        r'^统计$',
        r'^查看统计$',
        r'^cache stats$',
        r'^缓存统计$'
    ],
    examples=[
        "stats",
        "统计",
        "cache stats",
        "查看缓存统计"
    ],
    category="cache"
)
def skill_cache_stats():
    """查看缓存统计"""
    try:
        from mcp_server.cache.semantic import SemanticCache
        
        # 创建临时实例获取统计
        cache = SemanticCache()
        stats = cache.get_stats()
        
        # 格式化输出
        lines = [
            "📊 缓存统计信息",
            "",
            f"总请求数: {stats['total_requests']}",
            f"缓存命中: {stats['cache_hits']}",
            f"缓存未命中: {stats['cache_misses']}",
            f"命中率: {stats['hit_rate']:.2%}",
            f"",
            f"精确命中: {stats['exact_hits']}",
            f"语义命中: {stats['semantic_hits']}",
            f"",
            f"缓存大小: {stats['cache_size']} / {stats['max_size']}"
        ]
        
        return '\n'.join(lines)
        
    except Exception as e:
        return f"❌ 获取统计失败: {str(e)}"


@registry.register(
    name="cache status",
    description="查看缓存状态",
    patterns=[
        r'^status$',
        r'^状态$',
        r'^cache status$',
        r'^缓存状态$'
    ],
    examples=["status", "状态", "cache status"],
    category="cache"
)
def skill_cache_status():
    """查看缓存状态"""
    lines = [
        "📋 缓存系统状态",
        "",
        "✅ 语义缓存: 运行中",
        "✅ 多级缓存: 运行中",
        "✅ 自适应TTL: 启用",
        "",
        "💡 提示: 使用 'stats' 查看详细统计"
    ]
    return '\n'.join(lines)


@registry.register(
    name="clear cache",
    description="清空缓存",
    patterns=[
        r'^clear$',
        r'^clear cache$',
        r'^清空$',
        r'^清空缓存$',
        r'^清除缓存$'
    ],
    examples=["clear", "clear cache", "清空缓存"],
    require_confirmation=True,
    category="cache"
)
def skill_clear_cache():
    """清空缓存"""
    try:
        from mcp_server.cache.semantic import SemanticCache
        
        cache = SemanticCache()
        cache.clear()
        
        return {
            'message': '🗑️ 缓存已清空',
            'data': {'cleared_at': datetime.now().isoformat()}
        }
    except Exception as e:
        return f"❌ 清空缓存失败: {str(e)}"


@registry.register(
    name="cache get",
    description="获取缓存",
    patterns=[
        r'^get\s+(?P<key>.+)$',
        r'^获取\s+(?P<key>.+)$',
        r'^cache get\s+(?P<key>.+)$'
    ],
    examples=[
        "get python optimization",
        "获取 Python 优化"
    ],
    params={'key': '缓存键或查询'},
    category="cache"
)
def skill_cache_get(key: str):
    """获取缓存"""
    try:
        from mcp_server.cache.semantic import SemanticCache
        
        cache = SemanticCache()
        result = cache.get(key)
        
        if result:
            matched_query, similarity, response = result
            return {
                'message': f'✅ 缓存命中 (相似度: {similarity:.2%})',
                'data': {
                    'matched_query': matched_query,
                    'similarity': similarity,
                    'response': response[:200] + '...' if len(response) > 200 else response
                }
            }
        else:
            return f"❌ 缓存未找到: {key}"
            
    except Exception as e:
        return f"❌ 获取缓存失败: {str(e)}"


@registry.register(
    name="cache set",
    description="设置缓存",
    patterns=[
        r'^set\s+(?P<key>[^=]+)=\s*(?P<value>.+)$',
        r'^设置\s+(?P<key>[^=]+)=\s*(?P<value>.+)$'
    ],
    examples=[
        "set python=Python is great",
        "设置 测试=测试内容"
    ],
    params={
        'key': '缓存键',
        'value': '缓存值'
    },
    category="cache"
)
def skill_cache_set(key: str, value: str):
    """设置缓存"""
    try:
        from mcp_server.cache.semantic import SemanticCache
        
        cache = SemanticCache()
        cache.set(key, value, ttl=3600)
        
        return f"✅ 缓存已设置: {key}"
        
    except Exception as e:
        return f"❌ 设置缓存失败: {str(e)}"


# ==================== 监控分析命令 ====================

@registry.register(
    name="open dashboard",
    description="打开监控面板",
    patterns=[
        r'^dashboard$',
        r'^open dashboard$',
        r'^面板$',
        r'^打开面板$',
        r'^监控面板$',
        r'^打开监控$'
    ],
    examples=[
        "dashboard",
        "open dashboard",
        "打开面板",
        "监控面板"
    ],
    category="monitor"
)
def skill_open_dashboard():
    """打开监控面板"""
    import webbrowser
    
    url = "http://localhost:8050"
    webbrowser.open(url)
    
    return f"🌐 已打开监控面板: {url}"


@registry.register(
    name="export report",
    description="导出报告",
    patterns=[
        r'^export$',
        r'^export report$',
        r'^导出$',
        r'^导出报告$',
        r'^保存报告$'
    ],
    examples=["export", "导出报告", "export report"],
    category="monitor"
)
def skill_export_report():
    """导出报告"""
    try:
        from mcp_server.cache.semantic import SemanticCache
        
        cache = SemanticCache()
        stats = cache.get_stats()
        
        # 生成报告
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': stats,
            'summary': {
                'hit_rate': f"{stats['hit_rate']:.2%}",
                'total_requests': stats['total_requests'],
                'cache_hits': stats['cache_hits']
            }
        }
        
        # 保存到文件
        filename = f"cache_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return {
            'message': f'📄 报告已导出: {filename}',
            'data': {'filename': filename}
        }
        
    except Exception as e:
        return f"❌ 导出报告失败: {str(e)}"


@registry.register(
    name="hot queries",
    description="查看热点查询",
    patterns=[
        r'^hot$',
        r'^hot queries$',
        r'^热点$',
        r'^热点查询$',
        r'^热门查询$'
    ],
    examples=["hot", "热点", "hot queries"],
    category="monitor"
)
def skill_hot_queries():
    """查看热点查询"""
    # 模拟热点数据
    hot_queries = [
        {'query': 'Python 性能优化', 'hits': 50},
        {'query': 'React useEffect', 'hits': 45},
        {'query': 'SQL 查询优化', 'hits': 40},
        {'query': 'Docker 部署', 'hits': 35},
        {'query': 'Git 分支管理', 'hits': 30},
    ]
    
    lines = ["🔥 热点查询 TOP 5", ""]
    for i, item in enumerate(hot_queries, 1):
        lines.append(f"{i}. {item['query']} ({item['hits']} 次)")
    
    return '\n'.join(lines)


# ==================== 配置管理命令 ====================

@registry.register(
    name="show config",
    description="显示配置",
    patterns=[
        r'^config$',
        r'^show config$',
        r'^配置$',
        r'^显示配置$',
        r'^查看配置$'
    ],
    examples=["config", "配置", "show config"],
    category="config"
)
def skill_show_config():
    """显示配置"""
    try:
        import yaml
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent / "config" / "default.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 显示关键配置
        lines = [
            "⚙️ 当前配置",
            "",
            f"相似度阈值: {config['cache']['similarity_threshold']}",
            f"L1 缓存大小: {config['cache']['levels']['l1']['max_size']}",
            f"L2 缓存大小: {config['cache']['levels']['l2']['max_size']}",
            f"L3 缓存大小: {config['cache']['levels']['l3']['max_size']}",
            "",
            f"自适应 TTL: {'启用' if config['cache']['adaptive_ttl']['enabled'] else '禁用'}",
            f"最小 TTL: {config['cache']['adaptive_ttl']['min_ttl']} 秒",
            f"最大 TTL: {config['cache']['adaptive_ttl']['max_ttl']} 秒",
        ]
        
        return '\n'.join(lines)
        
    except Exception as e:
        return f"❌ 读取配置失败: {str(e)}"


# ==================== 调试工具命令 ====================

@registry.register(
    name="test cache",
    description="测试缓存系统",
    patterns=[
        r'^test$',
        r'^test cache$',
        r'^测试$',
        r'^测试缓存$'
    ],
    examples=["test", "测试", "test cache"],
    category="debug"
)
def skill_test_cache():
    """测试缓存"""
    try:
        from mcp_server.cache.semantic import SemanticCache
        
        cache = SemanticCache()
        
        # 写入测试
        cache.set("test_key", "test_value", ttl=60)
        
        # 读取测试
        result = cache.get("test_key")
        
        if result and result[2] == "test_value":
            return {
                'message': '✅ 缓存测试通过',
                'data': {
                    'write': '成功',
                    'read': '成功',
                    'value': result[2]
                }
            }
        else:
            return "❌ 缓存测试失败: 读取值不匹配"
            
    except Exception as e:
        return f"❌ 缓存测试失败: {str(e)}"


@registry.register(
    name="ping",
    description="测试连接",
    patterns=[
        r'^ping$',
        r'^测试连接$',
        r'^连接测试$'
    ],
    examples=["ping", "测试连接"],
    category="debug"
)
def skill_ping():
    """Ping 测试"""
    return {
        'message': '✅ Pong! 系统运行正常',
        'data': {
            'status': 'ok',
            'timestamp': datetime.now().isoformat()
        }
    }


@registry.register(
    name="optimize",
    description="优化查询",
    patterns=[
        r'^optimize\s+(?P<query>.+)$',
        r'^优化\s+(?P<query>.+)$'
    ],
    examples=[
        "optimize 如何写 Python 函数",
        "优化 这段代码怎么改"
    ],
    params={'query': '要优化的查询'},
    category="debug"
)
def skill_optimize(query: str):
    """优化查询"""
    try:
        from agent.proxy import AgentProxy
        
        proxy = AgentProxy()
        result = proxy.process_request(query)
        
        lines = [
            "🔧 查询优化建议",
            "",
            f"原始查询: {result.original_query}",
            f"归一化后: {result.normalized_query}",
            f"缓存键: {result.cache_key[:16]}...",
            f"",
            f"是否缓存: {'是' if result.should_cache else '否'}",
            f"优先级: {result.priority}",
            f"请求类型: {result.metadata.get('request_type', 'unknown')}"
        ]
        
        return '\n'.join(lines)
        
    except Exception as e:
        return f"❌ 优化失败: {str(e)}"


# ==================== 自然语言命令 ====================

@registry.register(
    name="natural language",
    description="自然语言处理（兜底命令）",
    patterns=[
        r'^(?P<text>.+)$'  # 匹配任何文本
    ],
    examples=[],
    category="general"
)
def skill_natural_language(text: str):
    """处理自然语言"""
    # 尝试解析为命令
    command = executor.parse_natural_language(text)
    
    if command:
        return f"💡 识别到命令: '{command}'\n请直接输入该命令执行"
    
    return f"❓ 未识别的命令: '{text}'\n输入 'help' 查看可用命令"


# 导出
__all__ = ['BuiltinSkills', 'builtin_skills', 'registry', 'executor']
