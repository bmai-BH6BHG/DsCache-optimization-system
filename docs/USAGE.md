# DeepSeek 缓存优化器 - 使用指南

## 目录

1. [快速开始](#快速开始)
2. [架构概览](#架构概览)
3. [核心功能](#核心功能)
4. [配置说明](#配置说明)
5. [TRAE 集成](#trae-集成)
6. [监控面板](#监控面板)
7. [性能优化](#性能优化)
8. [故障排除](#故障排除)

## 快速开始

### 1. 安装

```bash
# 克隆或下载项目
cd deepseek-cache-optimizer

# 运行安装脚本
python install.py

# 或手动安装
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 启动可视化面板
python -m dashboard.app

# 访问 http://localhost:8050
```

### 3. 配置 TRAE

将 `config/trae-config.json` 的内容添加到 TRAE 的 MCP 配置中。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      TRAE IDE                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   代码编辑器  │    │   对话面板   │    │   其他功能模块   │ │
│  └──────┬──────┘    └──────┬──────┘    └────────┬────────┘ │
│         │                  │                     │          │
│         └──────────────────┼─────────────────────┘          │
│                            │                                │
│                   ┌────────▼────────┐                       │
│                   │   智能体代理     │                       │
│                   │  (Agent Proxy)  │                       │
│                   └────────┬────────┘                       │
└────────────────────────────┼────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   MCP 服务      │
                    │  ┌───────────┐  │
                    │  │ 语义缓存   │  │
                    │  │ 多级缓存   │  │
                    │  │ 自适应TTL │  │
                    │  └───────────┘  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   可视化面板     │
                    │  (Dashboard)    │
                    └─────────────────┘
```

## 核心功能

### 1. 语义缓存

基于向量相似度的智能缓存，支持：
- 精确匹配
- 语义相似匹配（相似度阈值可配置）
- 自动过期清理

```python
from mcp_server.cache.semantic import SemanticCache

cache = SemanticCache(similarity_threshold=0.85)

# 存储
cache.set("如何优化 Python 代码", "响应内容...", ttl=3600)

# 查询（支持语义匹配）
result = cache.get("Python 性能优化方法")
# 返回: (matched_query, similarity, response)
```

### 2. 多级缓存

三级缓存架构：
- **L1**: 内存缓存（最快，容量小）
- **L2**: SQLite 缓存（中等速度，中等容量）
- **L3**: 文件缓存（较慢，容量大）

```python
from mcp_server.cache.multi_level import MultiLevelCache

cache = MultiLevelCache()

# 自动按 L1 -> L2 -> L3 顺序查找
value = cache.get("cache_key")

# 写入所有层级
cache.set("cache_key", "value", ttl=3600)
```

### 3. 自适应 TTL

根据访问模式自动调整缓存有效期：

```python
from mcp_server.cache.adaptive_ttl import AdaptiveTTLManager

ttl_manager = AdaptiveTTLManager()

# 获取自适应 TTL
ttl = ttl_manager.get_ttl("如何写 Python 函数")

# 记录命中/未命中
ttl_manager.record_hit(query)
ttl_manager.record_miss(query)
```

### 4. 智能体代理

请求拦截和改写：

```python
from agent.proxy import AgentProxy

proxy = AgentProxy()

# 处理请求
result = proxy.process_request(
    query="请问如何优化这段代码？",
    context="当前文件: main.py"
)

# 返回:
# - normalized_query: 归一化查询
# - cache_key: 缓存键
# - should_cache: 是否缓存
# - priority: 优先级
```

### 5. 缓存决策引擎

智能判断何时使用缓存：

```python
from agent.decision import CacheDecisionEngine

engine = CacheDecisionEngine()

# 做出决策
decision = engine.decide(
    query="用户查询",
    cache_hit=True,
    cache_age=300,
    query_similarity=0.95
)

# decision.decision: USE_CACHE / REFRESH_CACHE / SKIP_CACHE
# decision.confidence: 置信度
# decision.reason: 决策原因
```

## 配置说明

### 主配置文件

`config/default.yaml`:

```yaml
cache:
  # 语义相似度阈值 (0-1)
  similarity_threshold: 0.85
  
  # 多级缓存配置
  levels:
    l1:
      max_size: 1000
      ttl: 300
    l2:
      max_size: 10000
      ttl: 3600
    l3:
      max_size: 100000
      ttl: 86400
  
  # 自适应 TTL
  adaptive_ttl:
    enabled: true
    min_ttl: 60
    max_ttl: 604800
    hit_threshold: 5
    miss_threshold: 3

agent:
  interception:
    enabled: true
    normalize_whitespace: true
    canonicalize_code: true
  
  decision:
    min_confidence: 0.8
    max_retries: 3

dashboard:
  server:
    host: "127.0.0.1"
    port: 8050
  charts:
    update_interval: 5000
```

### 环境变量

```bash
# 配置文件路径
export DEEPSEEK_CACHE_CONFIG="./config/default.yaml"

# 数据目录
export DEEPSEEK_CACHE_DATA_DIR="./data"

# 日志级别
export DEEPSEEK_CACHE_LOG_LEVEL="INFO"
```

## TRAE 集成

### 配置步骤

1. **打开 TRAE 设置**
   - Windows: `File > Preferences > Settings`
   - macOS: `Code > Preferences > Settings`

2. **找到 MCP 配置**
   搜索 "MCP" 或找到 "Extensions > MCP"

3. **添加配置**

将以下内容添加到 MCP 服务器配置：

```json
{
  "mcpServers": {
    "deepseek-cache-optimizer": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "DEEPSEEK_CACHE_CONFIG": "./config/default.yaml",
        "DEEPSEEK_CACHE_DATA_DIR": "./data"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

4. **重启 TRAE**

5. **验证连接**
   - 打开 TRAE 输出面板
   - 查看 MCP 服务器日志
   - 确认 "deepseek-cache-optimizer" 已连接

### 使用方式

在 TRAE 中使用 DeepSeek 时，缓存优化器会自动：

1. **拦截请求** - 分析查询内容
2. **检查缓存** - 查找语义相似的缓存
3. **返回缓存** - 如果命中，直接返回缓存响应
4. **存储缓存** - 新响应自动存入缓存

## 监控面板

### 访问面板

```bash
python -m dashboard.app
```

打开浏览器访问: http://localhost:8050

### 面板功能

1. **实时指标**
   - 命中率
   - 缓存命中次数
   - 节省 Token 数
   - 平均响应时间

2. **趋势图表**
   - 命中率趋势（支持时间范围选择）
   - 缓存层级分布
   - 请求类型分布
   - 响应时间对比

3. **热点查询**
   - TOP 10 高频查询
   - 命中次数统计
   - 命中率分析

4. **控制面板**
   - 清空缓存
   - 刷新数据
   - 导出报告

### 自定义面板

```python
from dashboard.app import create_app

app = create_app()

# 自定义配置
app.app.layout = ...  # 自定义布局

# 运行
app.run(debug=True, port=8050)
```

## 性能优化

### 1. 调整相似度阈值

```yaml
cache:
  # 更严格的匹配
  similarity_threshold: 0.90
  
  # 更宽松的匹配
  similarity_threshold: 0.75
```

### 2. 优化缓存层级

```yaml
cache:
  levels:
    l1:
      max_size: 2000  # 增加内存缓存
      ttl: 600        # 延长 TTL
    l2:
      max_size: 50000  # 增加 SQLite 缓存
```

### 3. 自适应 TTL 调优

```yaml
cache:
  adaptive_ttl:
    hit_threshold: 3   # 更快增加 TTL
    miss_threshold: 5  # 更慢减少 TTL
    increment_factor: 2.0
```

### 4. 预加载策略

```python
from agent.decision import CacheDecisionEngine

engine = CacheDecisionEngine()

# 预测并预加载
predictions = engine.should_preload(
    current_query="当前查询",
    recent_queries=["历史查询1", "历史查询2"],
    pattern_confidence=0.7
)
```

## 故障排除

### 常见问题

#### 1. MCP 服务无法启动

**症状**: TRAE 显示 MCP 服务器连接失败

**解决**:
```bash
# 检查 Python 版本
python --version  # 需要 >= 3.8

# 检查依赖
pip list | grep mcp

# 手动启动测试
python -m mcp_server.server
```

#### 2. 缓存命中率低

**症状**: 命中率低于 50%

**解决**:
- 降低相似度阈值: `similarity_threshold: 0.75`
- 检查查询归一化是否正常
- 查看热点查询，优化缓存策略

#### 3. 内存占用过高

**症状**: 系统内存不足

**解决**:
```yaml
cache:
  levels:
    l1:
      max_size: 500  # 减少内存缓存大小
  embedding:
    device: "cpu"    # 使用 CPU 而非 GPU
```

#### 4. 响应时间过长

**症状**: 缓存查询慢

**解决**:
- 检查 L1 缓存命中率
- 优化 SQLite 索引
- 考虑使用 Redis 替代 SQLite

### 日志查看

```bash
# 查看日志
tail -f logs/deepseek_cache.log

# 启用调试模式
export DEEPSEEK_CACHE_LOG_LEVEL="DEBUG"
python -m mcp_server.server
```

### 调试模式

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 测试缓存
from mcp_server.cache.semantic import SemanticCache

cache = SemanticCache()
cache.set("测试查询", "测试响应")
result = cache.get("测试查询")
print(cache.get_stats())
```

## 最佳实践

### 1. 查询优化

- 使用标准化的编程语言名称
- 避免过长的查询（>500 字符）
- 去除敏感信息

### 2. 缓存策略

- 代码生成类查询：高优先级，长 TTL
- 调试类查询：中优先级，短 TTL
- 对话类查询：低优先级或不缓存

### 3. 监控维护

- 定期查看监控面板
- 分析热点查询模式
- 根据使用情况调整配置

### 4. 成本控制

- 关注 "节省 Token" 指标
- 优化缓存命中率
- 合理设置 TTL

## 高级用法

### 自定义缓存键

```python
from agent.proxy import AgentProxy

proxy = AgentProxy()

# 自定义缓存键生成
def custom_key_generator(query, context):
    # 自定义逻辑
    return f"custom:{hash(query)}"

proxy._generate_cache_key = custom_key_generator
```

### 扩展语义模型

```python
from mcp_server.cache.semantic import SemanticCache

# 使用其他模型
cache = SemanticCache(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device="cuda"  # 使用 GPU
)
```

### 集成外部存储

```python
from mcp_server.cache.multi_level import MultiLevelCache

# 使用 Redis 作为 L2
cache = MultiLevelCache(
    l2_config={
        'type': 'redis',
        'host': 'localhost',
        'port': 6379
    }
)
```

## 贡献指南

欢迎提交 Issue 和 PR！

### 开发流程

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 创建 Pull Request

### 代码规范

- 遵循 PEP 8
- 添加类型注解
- 编写单元测试
- 更新文档

## 许可证

MIT License
