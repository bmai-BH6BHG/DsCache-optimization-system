# DeepSeek 缓存优化器 - 项目结构

```
deepseek-cache-optimizer/
│
├── 📄 README.md                    # 项目说明文档
├── 📄 PROJECT_STRUCTURE.md         # 本文件 - 项目结构说明
├── 📄 requirements.txt             # Python 依赖
├── 📄 setup.py                     # 安装配置
├── 📄 install.py                   # 安装脚本
├── 📄 verify.py                    # 验证脚本
├── 📄 start.bat                    # Windows 启动脚本
│
├── 📁 config/                      # 配置文件
│   ├── default.yaml               # 默认配置
│   └── trae-config.json           # TRAE 集成配置
│
├── 📁 docs/                        # 文档
│   ├── USAGE.md                   # 详细使用指南
│   └── SKILL_GUIDE.md             # Skill 使用指南
│
├── 📁 mcp_server/                  # MCP 服务模块
│   ├── __init__.py
│   ├── server.py                  # 基础 MCP 服务器
│   ├── server_with_skills.py      # 集成 Skill 的 MCP 服务器
│   │
│   └── 📁 cache/                   # 缓存核心模块
│       ├── __init__.py
│       ├── semantic.py            # 语义缓存
│       ├── multi_level.py         # 多级缓存
│       └── adaptive_ttl.py        # 自适应 TTL
│
├── 📁 agent/                       # 智能体模块
│   ├── __init__.py
│   ├── proxy.py                   # 请求代理和拦截
│   ├── context.py                 # 上下文管理
│   └── decision.py                # 缓存决策引擎
│
├── 📁 skills/                      # Skill 系统
│   ├── __init__.py
│   ├── registry.py                # Skill 注册表
│   ├── executor.py                # Skill 执行器
│   ├── builtin_skills.py          # 内置 Skill 命令
│   ├── cli.py                     # CLI 工具
│   └── mcp_integration.py         # MCP 集成
│
├── 📁 dashboard/                   # 可视化面板
│   ├── __init__.py
│   └── app.py                     # Dash 应用
│
├── 📁 tests/                       # 测试
│   ├── test_cache.py              # 缓存模块测试
│   └── test_agent.py              # 智能体模块测试
│
└── 📁 data/                        # 数据目录（运行时创建）
    ├── cache_l2.db                # L2 SQLite 缓存
    ├── cache_l3/                  # L3 文件缓存
    └── logs/                      # 日志文件
```

## 核心模块详解

### 1. MCP 服务 (mcp_server/)

#### server.py
- 基础 MCP 协议实现
- 提供 6 个核心工具：
  - `cache_query`: 缓存查询
  - `cache_store`: 存储缓存
  - `get_stats`: 获取统计
  - `clear_cache`: 清空缓存
  - `optimize_query`: 优化查询
  - `predict_preload`: 预测预加载

#### server_with_skills.py
- 集成 Skill 系统的 MCP 服务器
- 额外提供 4 个 Skill 工具：
  - `skill_execute`: 执行 Skill 命令
  - `skill_list`: 列出所有 Skill
  - `skill_help`: 获取 Skill 帮助
  - `skill_parse`: 解析自然语言

#### cache/semantic.py
- 基于向量相似度的语义缓存
- 使用 sentence-transformers 计算文本嵌入
- 支持精确匹配和语义相似匹配
- 自动过期清理

#### cache/multi_level.py
- 三级缓存架构实现
- L1: 内存缓存（LRU 淘汰）
- L2: SQLite 缓存（持久化）
- L3: 文件缓存（大容量）
- 自动缓存提升/降级

#### cache/adaptive_ttl.py
- 根据访问模式动态调整 TTL
- 支持 4 种内容类型：代码、对话、文档、通用
- 自动增加/减少 TTL

### 2. 智能体模块 (agent/)

#### proxy.py
- 请求拦截和归一化
- 查询改写以提高缓存命中率
- 请求类型检测
- 缓存决策

#### context.py
- 对话历史管理
- 代码上下文跟踪
- 相关上下文检索

#### decision.py
- 智能缓存决策
- 4 种决策：使用缓存、刷新缓存、跳过缓存、预加载
- 预测预加载

### 3. Skill 系统 (skills/)

#### registry.py
- Skill 注册表
- 装饰器注册机制
- 命令匹配和参数提取
- 分类管理

#### executor.py
- Skill 执行器
- 执行状态管理
- 确认机制
- 自动补全建议

#### builtin_skills.py
- 18+ 个内置 Skill 命令
- 5 个分类：通用、缓存管理、监控分析、配置管理、调试工具
- 自然语言解析

#### cli.py
- 交互式命令行界面
- 结果格式化显示
- 建议提示

#### mcp_integration.py
- MCP 协议集成
- 4 个 MCP 工具封装
- 与 TRAE 无缝对接

### 4. 可视化面板 (dashboard/)

#### app.py
- Dash + Plotly 实现
- 实时指标监控
- 趋势图表
- 热点查询分析
- 控制面板

## 数据流

### 标准请求流程

```
用户查询
    ↓
智能体代理 (Agent Proxy)
    - 归一化查询
    - 检测请求类型
    - 生成缓存键
    ↓
MCP 服务
    - 检查语义缓存
    - 检查多级缓存
    ↓
缓存命中? 
    ├─ 是 → 返回缓存响应
    └─ 否 → 调用 DeepSeek API
              ↓
         存储到缓存
              ↓
         返回响应
```

### Skill 命令流程

```
用户输入命令
    ↓
Skill Registry
    - 匹配命令模式
    - 提取参数
    ↓
Skill Executor
    - 检查确认
    - 执行处理函数
    ↓
返回结果
    ↓
格式化输出
```

## 配置文件

### config/default.yaml

```yaml
# 应用配置
app:
  name: "DeepSeek Cache Optimizer"
  version: "1.0.0"

# MCP 服务配置
mcp:
  server:
    host: "127.0.0.1"
    port: 8080

# 缓存配置
cache:
  similarity_threshold: 0.85
  levels:
    l1: {max_size: 1000, ttl: 300}
    l2: {max_size: 10000, ttl: 3600}
    l3: {max_size: 100000, ttl: 86400}
  adaptive_ttl:
    enabled: true
    min_ttl: 60
    max_ttl: 604800

# 智能体配置
agent:
  interception:
    enabled: true
  decision:
    min_confidence: 0.8

# 可视化面板配置
dashboard:
  server:
    port: 8050
```

### config/trae-config.json

```json
{
  "mcpServers": {
    "deepseek-cache-optimizer": {
      "command": "python",
      "args": ["-m", "mcp_server.server_with_skills"],
      "env": {
        "DEEPSEEK_CACHE_CONFIG": "./config/default.yaml"
      }
    }
  }
}
```

## 关键指标

### 缓存性能
- **命中率**: 缓存命中 / 总请求
- **精确命中率**: 精确匹配命中 / 总请求
- **语义命中率**: 语义匹配命中 / 总请求
- **平均响应时间**: 缓存查询耗时

### 缓存分布
- **L1 命中率**: 内存缓存命中
- **L2 命中率**: SQLite 缓存命中
- **L3 命中率**: 文件缓存命中

### Skill 使用
- **命令执行次数**: 各 Skill 调用统计
- **自然语言解析成功率**: 自然语言转命令成功率
- **平均执行时间**: Skill 执行耗时

## 扩展点

### 1. 自定义 Skill

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

### 2. 自定义缓存存储

```python
from mcp_server.cache.multi_level import MultiLevelCache

cache = MultiLevelCache(
    l2_config={'type': 'redis', 'host': 'localhost'}
)
```

### 3. 自定义语义模型

```python
from mcp_server.cache.semantic import SemanticCache

cache = SemanticCache(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device="cuda"
)
```

## 调试技巧

### 1. 启用详细日志

```bash
export DEEPSEEK_CACHE_LOG_LEVEL=DEBUG
python -m mcp_server.server_with_skills
```

### 2. 测试缓存

```python
from mcp_server.cache.semantic import SemanticCache

cache = SemanticCache()
cache.set("test", "response")
print(cache.get_stats())
```

### 3. 测试 Skill

```bash
# 测试单个命令
python -m skills.cli test

# 查看帮助
python -m skills.cli help

# 交互模式
python -m skills.cli
```

### 4. 验证安装

```bash
python verify.py
```

## 性能优化建议

1. **调整相似度阈值**: 根据命中率调整 0.75-0.90
2. **优化缓存层级**: 增加 L1 大小，调整 TTL
3. **启用预加载**: 基于使用模式预测
4. **监控热点**: 分析高频查询，优化缓存策略
5. **使用 CLI**: 批量执行命令提高效率

## 故障排除

### 常见问题

1. **MCP 服务无法启动**
   - 检查 Python 版本 >= 3.8
   - 检查依赖安装
   - 查看日志文件

2. **Skill 命令未识别**
   - 检查命令拼写
   - 使用 `help` 查看可用命令
   - 尝试自然语言表述

3. **缓存命中率低**
   - 降低相似度阈值
   - 检查查询归一化
   - 分析热点查询

4. **内存占用过高**
   - 减少 L1 缓存大小
   - 使用 CPU 而非 GPU
   - 缩短 TTL

## 贡献指南

### 代码规范
- 遵循 PEP 8
- 添加类型注解
- 编写单元测试
- 更新文档

### 提交 PR
1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 创建 Pull Request

## 许可证

MIT License
