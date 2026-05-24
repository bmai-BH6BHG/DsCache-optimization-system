# DeepSeek 缓存优化器 - Skill 使用指南

## 概述

Skill 系统提供了自然语言命令接口，让你可以通过简单的命令快速操作 DeepSeek 缓存优化器。

## 使用方式

### 1. 命令行 CLI

```bash
# 启动 Skill CLI
python -m skills.cli

# 或直接执行单个命令
python -m skills.cli stats
python -m skills.cli "clear cache"
```

### 2. MCP 工具调用

在 TRAE 中通过 MCP 调用 Skill：

```json
{
  "tool": "skill_execute",
  "arguments": {
    "command": "stats"
  }
}
```

### 3. 自然语言

系统支持自然语言解析：

- "查看缓存统计" → `stats`
- "清空缓存" → `clear cache`
- "打开监控面板" → `open dashboard`

## 可用 Skill 命令

### 🎯 通用命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `hello` / `你好` | 问候 | `hello` |
| `help` / `帮助` | 显示帮助 | `help` / `help stats` |

### 💾 缓存管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `stats` / `统计` | 查看缓存统计 | `stats` |
| `status` / `状态` | 查看缓存状态 | `status` |
| `clear` / `清空缓存` | 清空缓存（需确认） | `clear cache` |
| `get <key>` | 获取缓存 | `get python` |
| `set <key>=<value>` | 设置缓存 | `set test=value` |

### 📊 监控分析

| 命令 | 说明 | 示例 |
|------|------|------|
| `dashboard` / `面板` | 打开监控面板 | `dashboard` |
| `export` / `导出报告` | 导出统计报告 | `export` |
| `hot` / `热点` | 查看热点查询 | `hot queries` |

### ⚙️ 配置管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `config` / `配置` | 显示当前配置 | `config` |

### 🔧 调试工具

| 命令 | 说明 | 示例 |
|------|------|------|
| `test` / `测试` | 测试缓存系统 | `test cache` |
| `ping` | 测试连接 | `ping` |
| `optimize <query>` | 优化查询 | `optimize 如何写函数` |

## 命令示例

### 查看缓存统计

```
🚀 Cache> stats

📊 缓存统计信息

总请求数: 1250
缓存命中: 938
缓存未命中: 312
命中率: 75.04%

精确命中: 500
语义命中: 438

缓存大小: 938 / 10000
```

### 清空缓存

```
🚀 Cache> clear cache

⚠️ 此操作需要确认
确认执行 'clear cache' 吗? (yes/no)

🚀 Cache> yes

🗑️ 缓存已清空
```

### 获取缓存

```
🚀 Cache> get python optimization

✅ 缓存命中 (相似度: 92.50%)

📊 数据: matched_query: 如何优化 Python 代码
  similarity: 0.925
  response: Python 性能优化建议：1. 使用列表推导式...
```

### 优化查询

```
🚀 Cache> optimize 请问如何写 Python 函数？谢谢！

🔧 查询优化建议

原始查询: 请问如何写 Python 函数？谢谢！
归一化后: 如何写 python 函数
缓存键: a1b2c3d4e5f6...

是否缓存: 是
优先级: 1
请求类型: code_generation
```

### 打开监控面板

```
🚀 Cache> dashboard

🌐 已打开监控面板: http://localhost:8050
```

## 自然语言支持

系统可以解析常见的自然语言指令：

| 自然语言 | 对应命令 |
|----------|----------|
| 查看缓存统计 / 显示数据 | `stats` |
| 清空缓存 / 清除缓存 | `clear cache` |
| 打开面板 / 启动监控 | `open dashboard` |
| 导出报告 / 保存数据 | `export report` |
| 查看热点 / 热门查询 | `hot queries` |
| 测试缓存 / 检查系统 | `test cache` |

## 在 TRAE 中使用

### 通过 MCP 调用

在 TRAE 的 DeepSeek 对话中，你可以直接调用 Skill：

```
用户: 查看缓存统计

AI: [调用 skill_execute 工具]
    命令: stats
    
结果:
📊 缓存统计信息
总请求数: 1250
缓存命中: 938
命中率: 75.04%
```

### 自然语言触发

TRAE 可以自动识别你的意图：

```
用户: 帮我看看缓存命中率怎么样

AI: [解析为 "stats" 命令]
    
结果:
📊 当前缓存命中率为 75.04%，
    共处理 1250 个请求，命中 938 次。
```

## 自定义 Skill

你可以轻松添加自己的 Skill：

```python
from skills.registry import registry

@registry.register(
    name="my_skill",
    description="我的自定义 Skill",
    patterns=[r'^mycommand\s+(?P<arg>.+)$'],
    examples=["mycommand test"],
    category="custom"
)
def my_skill_handler(arg: str):
    return f"处理参数: {arg}"
```

## 自动补全

在 CLI 中，输入部分命令会显示建议：

```
🚀 Cache> sta

💡 你可能想输入:
  • stats
  • status
```

## 批量执行

你可以通过脚本批量执行命令：

```bash
# 创建命令文件
cat > commands.txt << EOF
stats
status
hot
config
EOF

# 批量执行
while read cmd; do
    python -m skills.cli "$cmd"
done < commands.txt
```

## 集成到工作流

### Git Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
python -m skills.cli "export report"
git add cache_report_*.json
```

### CI/CD

```yaml
# .github/workflows/cache-report.yml
- name: Generate Cache Report
  run: python -m skills.cli export
```

## 故障排除

### 命令未识别

```
🚀 Cache> unknown command

❓ 未识别的命令: 'unknown command'
输入 'help' 查看可用命令

💡 你可能想输入:
  • help
  • hot
  • status
```

### 需要确认的操作

危险操作（如清空缓存）需要确认：

```
🚀 Cache> clear cache

⚠️ 此操作需要确认
确认执行 'clear cache' 吗? (yes/no)

🚀 Cache> yes  # 或 no 取消
```

### 获取帮助

```
🚀 Cache> help

📚 DeepSeek 缓存优化器 - Skill 列表

【通用】
  • hello: 问候命令
  • help: 显示帮助信息

【缓存管理】
  • cache stats: 查看缓存统计信息
  • cache status: 查看缓存状态
  • clear cache: 清空缓存
  ...

💡 使用提示: 输入 'help <skill_name>' 查看详细用法
```

## 最佳实践

1. **使用自然语言** - 让 TRAE 自动解析你的意图
2. **定期查看统计** - 使用 `stats` 监控缓存效果
3. **导出报告** - 使用 `export` 保存历史数据
4. **测试缓存** - 使用 `test` 验证系统状态
5. **优化查询** - 使用 `optimize` 分析查询质量

## 进阶用法

### 组合命令

```bash
# 导出报告并清空缓存
python -m skills.cli export && python -m skills.cli "clear cache"
```

### 定时任务

```bash
# crontab -e
# 每小时导出报告
0 * * * * cd /path/to/deepseek-cache-optimizer && python -m skills.cli export
```

### API 调用

```python
from skills.executor import executor
import asyncio

async def main():
    result = await executor.execute("stats")
    print(result.message)

asyncio.run(main())
```

## 总结

Skill 系统让 DeepSeek 缓存优化器的使用变得简单直观。无论是通过 CLI、MCP 还是自然语言，你都可以轻松管理和监控缓存系统。

更多帮助请查看：
- `help` - 所有可用命令
- `help <command>` - 具体命令帮助
- `test` - 测试系统状态
