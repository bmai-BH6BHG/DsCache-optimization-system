"""
Skill CLI - 命令行交互工具
"""

import asyncio
import sys
from typing import Optional

from .executor import executor, ExecutionStatus
from .builtin_skills import registry


class SkillCLI:
    """Skill 命令行界面"""
    
    def __init__(self):
        self.running = False
        self.prompt = "🚀 Cache> "
    
    async def run(self):
        """运行 CLI"""
        self.running = True
        
        print("🚀 DeepSeek 缓存优化器 - Skill CLI")
        print("输入 'help' 查看可用命令，输入 'exit' 退出\n")
        
        while self.running:
            try:
                # 获取输入
                command = input(self.prompt).strip()
                
                if not command:
                    continue
                
                # 退出命令
                if command.lower() in ['exit', 'quit', '退出', 'q']:
                    print("👋 再见！")
                    break
                
                # 执行命令
                result = await executor.execute(command)
                
                # 显示结果
                self._display_result(result)
                
            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except EOFError:
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
        
        self.running = False
    
    def _display_result(self, result):
        """显示执行结果"""
        if result.status == ExecutionStatus.SUCCESS:
            print(result.message)
            
            # 显示额外数据
            if result.data:
                print(f"\n📊 数据:")
                for key, value in result.data.items():
                    print(f"  {key}: {value}")
        
        elif result.status == ExecutionStatus.CONFIRMATION_REQUIRED:
            print(f"\n{result.message}")
            print(result.confirmation_prompt)
        
        elif result.status == ExecutionStatus.NOT_FOUND:
            print(f"❓ {result.message}")
            
            # 显示建议
            suggestions = executor.get_suggestions(result.message.split(":")[-1].strip().strip("'"))
            if suggestions:
                print("\n💡 你可能想输入:")
                for sugg in suggestions[:5]:
                    print(f"  • {sugg['name']}")
        
        elif result.status == ExecutionStatus.ERROR:
            print(f"❌ {result.message}")
        
        print()  # 空行
    
    async def execute_single(self, command: str):
        """执行单个命令"""
        result = await executor.execute(command)
        self._display_result(result)
        return result


def main():
    """主入口"""
    cli = SkillCLI()
    
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        # 执行单个命令
        command = ' '.join(sys.argv[1:])
        asyncio.run(cli.execute_single(command))
    else:
        # 运行交互模式
        asyncio.run(cli.run())


if __name__ == "__main__":
    main()
