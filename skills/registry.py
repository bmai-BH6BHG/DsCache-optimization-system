"""
Skill 注册表 - 管理和注册 Skill
"""

import re
from typing import Dict, List, Callable, Optional, Any, Pattern
from dataclasses import dataclass, field
from functools import wraps


@dataclass
class Skill:
    """Skill 定义"""
    name: str                          # Skill 名称
    description: str                   # Skill 描述
    patterns: List[Pattern]            # 匹配模式（正则表达式）
    handler: Callable                  # 处理函数
    examples: List[str] = field(default_factory=list)  # 使用示例
    params: Dict[str, Any] = field(default_factory=dict)  # 参数定义
    require_confirmation: bool = False  # 是否需要确认
    category: str = "general"          # 分类


class SkillRegistry:
    """Skill 注册表"""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(
        self,
        name: str,
        description: str,
        patterns: List[str],
        examples: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        require_confirmation: bool = False,
        category: str = "general"
    ):
        """注册 Skill 的装饰器"""
        def decorator(func: Callable) -> Callable:
            # 编译正则表达式
            compiled_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
            
            skill = Skill(
                name=name,
                description=description,
                patterns=compiled_patterns,
                handler=func,
                examples=examples or [],
                params=params or {},
                require_confirmation=require_confirmation,
                category=category
            )
            
            self._skills[name] = skill
            
            # 添加到分类
            if category not in self._categories:
                self._categories[category] = []
            if name not in self._categories[category]:
                self._categories[category].append(name)
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def match(self, command: str) -> Optional[tuple]:
        """
        匹配命令
        
        Returns:
            (skill_name, params) 或 None
        """
        for name, skill in self._skills.items():
            for pattern in skill.patterns:
                match = pattern.match(command)
                if match:
                    # 提取参数
                    params = match.groupdict()
                    return (name, params)
        
        return None
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取 Skill"""
        return self._skills.get(name)
    
    def get_skills_by_category(self, category: str) -> List[Skill]:
        """获取分类下的所有 Skill"""
        skill_names = self._categories.get(category, [])
        return [self._skills[name] for name in skill_names if name in self._skills]
    
    def list_skills(self) -> Dict[str, List[Skill]]:
        """列出所有 Skill"""
        result = {}
        for category, names in self._categories.items():
            result[category] = [self._skills[name] for name in names if name in self._skills]
        return result
    
    def get_help_text(self, skill_name: Optional[str] = None) -> str:
        """获取帮助文本"""
        if skill_name:
            skill = self._skills.get(skill_name)
            if skill:
                return self._format_skill_help(skill)
            return f"未找到 Skill: {skill_name}"
        
        # 返回所有 Skill 的帮助
        lines = ["📚 DeepSeek 缓存优化器 - Skill 列表\n"]
        
        for category, skills in self.list_skills().items():
            lines.append(f"\n【{self._get_category_name(category)}】")
            for skill in skills:
                lines.append(f"  • {skill.name}: {skill.description}")
        
        lines.append("\n💡 使用提示: 输入 'help <skill_name>' 查看详细用法")
        return "\n".join(lines)
    
    def _format_skill_help(self, skill: Skill) -> str:
        """格式化单个 Skill 的帮助"""
        lines = [
            f"📖 {skill.name}",
            f"描述: {skill.description}",
            f"分类: {self._get_category_name(skill.category)}",
            "",
            "使用示例:"
        ]
        
        for example in skill.examples:
            lines.append(f"  • {example}")
        
        if skill.params:
            lines.extend(["", "参数:"])
            for param_name, param_info in skill.params.items():
                lines.append(f"  • {param_name}: {param_info}")
        
        return "\n".join(lines)
    
    def _get_category_name(self, category: str) -> str:
        """获取分类中文名"""
        names = {
            "general": "通用",
            "cache": "缓存管理",
            "monitor": "监控分析",
            "config": "配置管理",
            "debug": "调试工具"
        }
        return names.get(category, category)


# 全局注册表实例
registry = SkillRegistry()
