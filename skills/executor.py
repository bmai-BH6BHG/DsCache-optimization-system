"""
Skill 执行器 - 执行匹配的 Skill
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from .registry import SkillRegistry, registry


class ExecutionStatus(Enum):
    """执行状态"""
    SUCCESS = "success"
    ERROR = "error"
    CONFIRMATION_REQUIRED = "confirmation_required"
    NOT_FOUND = "not_found"
    INVALID_PARAMS = "invalid_params"


@dataclass
class ExecutionResult:
    """执行结果"""
    status: ExecutionStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    skill_name: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None


class SkillExecutor:
    """Skill 执行器"""
    
    def __init__(self, registry: SkillRegistry = None):
        self.registry = registry or SkillRegistry()
        self._pending_confirmations: Dict[str, Dict] = {}
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """设置执行上下文"""
        self._context.update(kwargs)
    
    async def execute(self, command: str, confirmed: bool = False) -> ExecutionResult:
        """
        执行命令
        
        Args:
            command: 用户输入的命令
            confirmed: 是否已确认（用于需要确认的操作）
        
        Returns:
            ExecutionResult: 执行结果
        """
        # 检查是否是确认操作
        if command.lower() in ['yes', 'y', '确认', '是']:
            return await self._handle_confirmation(True)
        elif command.lower() in ['no', 'n', '取消', '否']:
            return await self._handle_confirmation(False)
        
        # 匹配 Skill
        match_result = self.registry.match(command)
        
        if not match_result:
            return ExecutionResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"未识别的命令: '{command}'\n输入 'help' 查看可用命令"
            )
        
        skill_name, params = match_result
        skill = self.registry.get_skill(skill_name)
        
        if not skill:
            return ExecutionResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"Skill 未找到: {skill_name}"
            )
        
        # 检查是否需要确认
        if skill.require_confirmation and not confirmed:
            self._pending_confirmations[skill_name] = {
                'command': command,
                'params': params,
                'skill': skill
            }
            
            return ExecutionResult(
                status=ExecutionStatus.CONFIRMATION_REQUIRED,
                message=f"⚠️ 此操作需要确认",
                skill_name=skill_name,
                requires_confirmation=True,
                confirmation_prompt=f"确认执行 '{skill_name}' 吗? (yes/no)"
            )
        
        # 执行 Skill
        try:
            # 合并上下文和参数
            execution_params = {**self._context, **params}
            
            # 调用处理函数
            if asyncio.iscoroutinefunction(skill.handler):
                result = await skill.handler(**execution_params)
            else:
                result = skill.handler(**execution_params)
            
            # 处理返回值
            if isinstance(result, dict):
                message = result.get('message', '执行成功')
                data = result.get('data')
            elif isinstance(result, str):
                message = result
                data = None
            else:
                message = '执行成功'
                data = result
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=message,
                data=data,
                skill_name=skill_name
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message=f"执行失败: {str(e)}",
                skill_name=skill_name
            )
    
    async def _handle_confirmation(self, confirmed: bool) -> ExecutionResult:
        """处理确认操作"""
        if not self._pending_confirmations:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                message="没有待确认的操作"
            )
        
        # 获取最近的待确认操作
        skill_name = list(self._pending_confirmations.keys())[-1]
        pending = self._pending_confirmations.pop(skill_name)
        
        if not confirmed:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="操作已取消",
                skill_name=skill_name
            )
        
        # 重新执行，标记为已确认
        return await self.execute(pending['command'], confirmed=True)
    
    def get_suggestions(self, partial_command: str) -> list:
        """
        获取命令建议（自动补全）
        
        Args:
            partial_command: 部分输入的命令
        
        Returns:
            建议列表
        """
        suggestions = []
        
        for skill in self.registry._skills.values():
            # 检查名称匹配
            if skill.name.lower().startswith(partial_command.lower()):
                suggestions.append({
                    'name': skill.name,
                    'description': skill.description,
                    'type': 'skill'
                })
            
            # 检查示例匹配
            for example in skill.examples:
                if partial_command.lower() in example.lower():
                    suggestions.append({
                        'name': example,
                        'description': f"来自: {skill.name}",
                        'type': 'example'
                    })
        
        return suggestions[:10]  # 最多返回 10 个建议
    
    def parse_natural_language(self, text: str) -> Optional[str]:
        """
        解析自然语言为命令
        
        Args:
            text: 自然语言文本
        
        Returns:
            对应的命令或 None
        """
        # 常见的自然语言映射
        mappings = {
            r'(查看|显示|获取).*(统计|指标|数据)': 'stats',
            r'(清空|清除|删除).*(缓存|cache)': 'clear cache',
            r'(查看|显示).*(缓存|cache).*(状态|情况)': 'cache status',
            r'(优化|改进).*(查询|query)': 'optimize',
            r'(打开|启动|查看).*(面板|dashboard|监控)': 'open dashboard',
            r'(导出|保存).*(报告|report|数据)': 'export report',
            r'(测试|检查).*(缓存|系统)': 'test cache',
            r'(帮助|help|怎么使用)': 'help',
        }
        
        import re
        for pattern, command in mappings.items():
            if re.search(pattern, text, re.IGNORECASE):
                return command
        
        return None


# 全局执行器实例
executor = SkillExecutor(registry)
