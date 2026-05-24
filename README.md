# DeepSeek Cache Optimizer

**OpenAI 兼容的智能缓存中继服务** — 自动缓存 API 响应、降低延迟与成本、实时监控命中率。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 为什么需要？

每次向 DeepSeek（或其他兼容 API）发送相同或相似的问题，都会重新计算、重新计费。DeepSeek Cache Optimizer 在客户端与上游 API 之间充当**透明中继层**：

- 🚀 **相同问题**：< 5ms 从缓存返回，完全不消耗 API 额度
- 🧠 **相似问题**：通过 Jaccard 语义匹配复用缓存结果
- 📊 **实时监控**：内置仪表板展示命中率、响应时间、节省的 Token

### 效果对比

| 场景 | 直连 API | 通过中继 |
|------|----------|----------|
| 首次请求 | ~500ms | ~500ms |
| 相同问题再次请求 | ~500ms | **< 5ms** |
| 相似问题 | ~500ms | **< 10ms** |
| API 成本 | 每次付费 | 仅首次付费 |

---

## 快速开始

### 1. 安装依赖

```bash
cd deepseek-cache-optimizer
pip install -r requirements.txt
```

**最简安装**（仅需中继服务）：
```bash
pip install fastapi uvicorn requests
```

### 2. 启动服务

```bash
python relay_server.py
```

```
============================================================
  SK 密钥:  sk-b11d27372dc729ee8840067d31eb51a1ad08d8f85c1b004b
  上游 API:  https://api.deepseek.com
  模型:      deepseek-v4-flash
============================================================
Relay server: http://127.0.0.1:8001
Dashboard:   http://127.0.0.1:8001
```

### 3. 配置上游 API Key

打开浏览器访问 `http://127.0.0.1:8001`，在「API 配置」页签中填写：

| 配置项 | 说明 |
|--------|------|
| API Base URL | 上游地址，默认 `https://api.deepseek.com` |
| API Key | 你的 DeepSeek API 密钥 |
| 默认模型 | `deepseek-v4-flash`（推荐） |

点击「保存配置」。

### 4. 配置客户端

以 Trae（或其他 OpenAI 兼容客户端）为例：

| 配置项 | 值 |
|--------|-----|
| API Base URL | `http://127.0.0.1:8001/v1` |
| API Key | 仪表板显示的 SK 密钥 |
| 模型 | `deepseek-v4-flash` |

---

## 架构

```
┌──────────┐     Bearer SK      ┌──────────────┐     API Key      ┌──────────────┐
│  Client  │ ────────────────── │   中继服务    │ ─────────────── │  DeepSeek    │
│  (Trae)  │ ◀────────────────── │    :8001     │ ◀─────────────── │  (或其他)     │
└──────────┘    OpenAI 格式      └──────────────┘   上游转发        └──────────────┘
                                       │
                                   ┌───┴───┐
                                   │ Cache │
                                   │  SQL  │
                                   └───────┘
```

### 缓存策略（三阶段）

```
用户问题
    │
    ▼
┌─────────────────────┐
│ 1. 精确哈希匹配      │  MD5(问题) → O(1) 查找  → < 5ms
│    TTL: 7 天         │
└─────────┬───────────┘
          │ 未命中
          ▼
┌─────────────────────┐
│ 2. Jaccard 相似度    │  bigram 字符级相似度  → < 10ms
│    阈值: > 0.55      │  匹配已有缓存文本
└─────────┬───────────┘
          │ 未命中
          ▼
┌─────────────────────┐
│ 3. 上游 API 转发     │  调用 DeepSeek API    → ~500ms
│    (存入缓存)         │  结果自动持久化到 SQLite
└─────────────────────┘
```

### 请求类型自动分类

系统自动将每次请求分类，用于监控统计：

- `code_generation` — 代码生成/编写
- `debugging` — 调试/报错修复
- `code_explanation` — 代码解释/概念说明
- `conversation` — 日常对话（你好/谢谢等）
- `general_qa` — 通用问答

---

## 记忆系统与知识库

### 记忆系统（灵感来自 Mem0）

系统内置轻量级记忆层，自动记录对话历史：

**记忆类型**：
- `episodic` — 事件记忆（对话记录）
- `semantic` — 语义记忆（知识点）
- `procedural` — 流程记忆（操作步骤）
- `preference` — 偏好记忆（用户偏好）

**自动集成**：
- 缓存命中时自动记录到记忆系统
- 新请求时自动搜索相关记忆作为上下文

**使用示例**：

```bash
# 添加记忆
curl -X POST http://127.0.0.1:8001/api/memory/add \
  -H "Content-Type: application/json" \
  -d '{"content": "用户偏好使用 TypeScript", "memory_type": "preference"}'

# 搜索记忆
curl "http://127.0.0.1:8001/api/memory/search?query=TypeScript"
```

### 知识库

存储项目知识、技术文档、最佳实践等：

**使用示例**：

```bash
# 添加知识
curl -X POST http://127.0.0.1:8001/api/knowledge/add \
  -H "Content-Type: application/json" \
  -d '{"title": "React Hooks 最佳实践", "content": "...", "category": "frontend", "tags": ["react", "hooks"]}'

# 搜索知识
curl "http://127.0.0.1:8001/api/knowledge/search?query=react hooks"
```

**知识分类建议**：
- `frontend` — 前端开发
- `backend` — 后端开发
- `devops` — 运维部署
- `architecture` — 架构设计
- `general` — 通用知识

---

## API 端点

### OpenAI 兼容端点（需要 SK 认证）

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/v1/models` | 模型列表 |
| `POST` | `/v1/chat/completions` | 聊天补全（支持 stream） |

### 管理端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/admin/config` | 查看当前配置 |
| `POST` | `/admin/config` | 更新配置（上游 URL/Key/模型） |
| `POST` | `/admin/reset-sk` | 重新生成 SK 密钥 |

### 监控端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/metrics` | 缓存统计快照 |
| `GET` | `/api/history?hours=24` | 命中率时间序列 |
| `GET` | `/api/cache-levels` | 各级缓存命中数 |
| `GET` | `/api/hot-queries` | 热门查询 Top 10 |

### 记忆系统端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/memory/stats` | 记忆系统统计 |
| `GET` | `/api/memory/list` | 获取记忆列表 |
| `GET` | `/api/memory/search?query=xxx` | 搜索记忆 |
| `POST` | `/api/memory/add` | 添加记忆 |
| `DELETE` | `/api/memory/{id}` | 删除记忆 |

### 知识库端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/knowledge/list` | 获取知识列表 |
| `GET` | `/api/knowledge/search?query=xxx` | 搜索知识 |
| `POST` | `/api/knowledge/add` | 添加知识 |
| `PUT` | `/api/knowledge/{id}` | 更新知识 |
| `DELETE` | `/api/knowledge/{id}` | 删除知识 |

---

## 仪表板

内置单文件 HTML 仪表板，无需额外安装：

```
http://127.0.0.1:8001
```

包含两个页签：

**API 配置** — 管理 SK 密钥、上游 API 配置、复制/重置 SK

**监控面板** — 实时展示：
- 命中率、缓存命中数、节省 Token、总请求数
- 命中率历史时序图
- 缓存 vs API 响应时间对比柱状图
- 请求类型分布饼图
- 热门查询排行榜

---

## 项目结构

```
deepseek-cache-optimizer/
├── relay_server.py          # 核心中继服务（单文件，生产就绪）
├── memory_system.py         # 记忆系统与知识库模块
├── dashboard.html           # 内置仪表板（单文件 HTML）
├── requirements.txt         # Python 依赖
├── config/
│   └── default.yaml         # 默认配置模板
├── mcp_server/              # MCP 协议缓存工具（进阶用法）
│   ├── server.py
│   └── cache/
│       ├── semantic.py      # 语义相似度缓存
│       ├── multi_level.py   # L1/L2/L3 多级缓存
│       └── adaptive_ttl.py  # 自适应 TTL
├── agent/                   # 查询改写与决策引擎
├── dashboard/               # Dash 全功能面板（可选）
├── data/                    # 运行时数据（自动创建）
│   ├── config.json          # 运行时配置
│   ├── response_cache.db    # 响应缓存（SQLite）
│   ├── memory.db            # 记忆系统数据库
│   ├── knowledge.db         # 知识库数据库
│   ├── metrics.db           # 指标历史
│   └── cache_stats.json     # 统计快照
└── tests/                   # 测试文件
```

---

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **缓存存储**: SQLite（持久化）
- **缓存算法**: MD5 哈希精确匹配 + Jaccard bigram 相似度
- **前端**: 原生 HTML + Plotly.js
- **兼容性**: 完全兼容 OpenAI API 格式

---

## License

MIT

---

*让每一次 API 调用都物有所值。*
