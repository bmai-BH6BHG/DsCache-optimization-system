"""
MCP Skill 集成 - 将 Skill 系统接入 MCP 服务
"""

from typing import Dict, List, Any
from mcp.types import Tool, TextContent

from .executor import executor, ExecutionStatus
from .registry import registry


class MCPSkillIntegration:
    """MCP Skill 集成"""
    
    def __init__(self):
        self.executor = executor
    
    def get_tools(self) -> List[Tool]:
        """获取 MCP 工具列表"""
        tools = []
        
        # 添加 Skill 执行工具
        tools.append(Tool(
            name="skill_execute",
            description="执行 Skill 命令",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令"
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "是否已确认",
                        "default": False
                    }
                },
                "required": ["command"]
            }
        ))
        
        # 添加 Skill 列表工具
        tools.append(Tool(
            name="skill_list",
            description="列出所有可用 Skill",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "分类筛选（可选）"
                    }
                }
            }
        ))
        
        # 添加 Skill 帮助工具
        tools.append(Tool(
            name="skill_help",
            description="获取 Skill 帮助",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Skill 名称（可选）"
                    }
                }
            }
        ))
        
        # 添加自然语言解析工具
        tools.append(Tool(
            name="skill_parse",
            description="解析自然语言为命令",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "自然语言文本"
                    }
                },
                "required": ["text"]
            }
        ))
        
        return tools
    
    async def execute_tool(self, name: str, arguments: Dict) -> List[TextContent]:
        """执行 MCP 工具"""
        if name == "skill_execute":
            return await self._handle_execute(arguments)
        elif name == "skill_list":
            return self._handle_list(arguments)
        elif name == "skill_help":
            return self._handle_help(arguments)
        elif name == "skill_parse":
            return self._handle_parse(arguments)
        else:
            return [TextContent(
                type="text",
                text=f"未知工具: {name}"
            )]
    
    async def _handle_execute(self, arguments: Dict) -> List[TextContent]:
        """处理执行命令"""
        command = arguments.get("command", "")
        confirmed = arguments.get("confirmed", False)
        
        result = await self.executor.execute(command, confirmed)
        
        response = {
            "status": result.status.value,
            "message": result.message,
            "skill_name": result.skill_name
        }
        
        if result.data:
            response["data"] = result.data
        
        if result.requires_confirmation:
            response["requires_confirmation"] = True
            response["confirmation_prompt"] = result.confirmation_prompt
        
        import json
        return [TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2)
        )]
    
    def _handle_list(self, arguments: Dict) -> List[TextContent]:
        """处理列表命令"""
        category = arguments.get("category")
        
        if category:
            skills = registry.get_skills_by_category(category)
        else:
            skills_dict = registry.list_skills()
            skills = []
            for cat_skills in skills_dict.values():
                skills.extend(cat_skills)
        
        result = []
        for skill in skills:
            result.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "examples": skill.examples[:3]  # 最多 3 个示例
            })
        
        import json
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]
    
    def _handle_help(self, arguments: Dict) -> List[TextContent]:
        """处理帮助命令"""
        skill_name = arguments.get("skill_name")
        help_text = registry.get_help_text(skill_name)
        
        return [TextContent(
            type="text",
            text=help_text
        )]
    
    def _handle_parse(self, arguments: Dict) -> List[TextContent]:
        """处理解析命令"""
        text = arguments.get("text", "")
        command = self.executor.parse_natural_language(text)
        
        result = {
            "original_text": text,
            "parsed_command": command,
            "success": command is not None
        }
        
        import json
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]


# 全局实例
mcp_skill_integration = MCPSkillIntegration()
