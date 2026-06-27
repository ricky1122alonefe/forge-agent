# Observability Dashboard — 设计文档

> **定位**：forge-agent 的可视化运维面板（MVP 完整版）
> **目标用户**：开发者、运维、研究员
> **决策日期**：2026-06-27

---

## 🎯 设计目标

### 核心问题

`forge-agent` 现在有了：
- 87 个文件、59 个测试、15 个 CLI 命令
- 动态生成的 agent（落盘到 `generated_agents/`）
- 结构化日志（FORGE_LOG_JSON）
- 内存里的 MetricsCollector + EventBus
- MANIFEST.json（所有 agent + 版本的元数据）

**但用户没有眼睛**。CLI 输出是流式的，看不到：
- 哪些 agent 在跑、跑得怎么样
- 历史 run 的 verdict 分布
- 哪个 agent 最近失败
- 生成代码的版本演变

### 解决目标

**一个本地 web 面板**：
- 跑 `forge-agent dashboard` → 浏览器开 `http://localhost:8765`
- 看 agent 列表 / 状态 / 历史 run / 实时日志
- 不需要 Docker / 不需要 Node / 不需要单独数据库

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│  Browser (HTMX + Alpine.js + Tailwind CDN)              │
│  - Agent 列表页 / Detail 页 / 实时日志                  │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP + WebSocket
┌────────────────────┴────────────────────────────────────┐
│  forge_agent.dashboard (FastAPI)                        │
│  - Jinja2 模板渲染                                       │
│  - WebSocket 推送实时事件                                │
│  - REST API 供 HTMX 调用                                 │
└────┬─────────────┬─────────────┬────────────┬───────────┘
     │             │             │            │
┌────┴─────┐ ┌────┴─────┐ ┌─────┴────┐ ┌──────┴──────┐
│ Manifest │ │  Log     │ │ Metrics  │ │   Agent     │
│  Store   │ │ Tailer   │ │Collector │ │  Registry   │
│ (JSON)   │ │ (file)   │ │ (in-mem) │ │  (singleton)│
└──────────┘ └──────────┘ └──────────┘ └─────────────┘
```

**关键决策**：

| 维度 | MVP | 升级路径 |
|---|---|---|
| **前端** | Jinja2 + HTMX + Tailwind CDN | 后续可加 React SPA |
| **后端** | FastAPI + uvicorn | 升级到 gunicorn 多 worker |
| **数据** | JSON 文件 + 内存 | 升级到 SQLite / Postgres |
| **实时** | WebSocket | 升级到 SSE / Kafka |
| **部署** | `forge-agent dashboard` 单命令 | 升级到 Docker / K8s |

---

## 📁 文件结构

```
src/forge_agent/dashboard/
├── __init__.py
├── app.py              # FastAPI app factory
├── server.py           # uvicorn 启动入口
├── routes/
│   ├── __init__.py
│   ├── pages.py        # 页面路由（GET /, /agents/<id>）
│   ├── api.py          # REST API（供 HTMX 局部刷新）
│   └── ws.py           # WebSocket（实时日志推送）
├── data/
│   ├── __init__.py
│   ├── manifest.py     # 读 MANIFEST.json → Agent / Version 数据类
│   ├── logs.py         # tail log file, parse JSON
│   ├── metrics.py      # 包装 MetricsCollector
│   └── runs.py         # 读 AgentReport 历史
├── templates/
│   ├── base.html       # 布局（导航 / 顶栏）
│   ├── index.html      # 首页（agent 列表）
│   ├── agent_detail.html
│   └── partials/
│       ├── agent_card.html
│       ├── log_line.html
│       └── metrics_panel.html
└── static/
    ├── htmx.min.js     # 本地引用（或 CDN）
    └── forge.css       # 项目专属样式
```

---

## 🎨 UI 设计

### Page 1: 首页（Agent 列表）

```
┌────────────────────────────────────────────────────────────┐
│ forge-agent Dashboard    [Agents] [Logs] [Metrics] [About] │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Overview                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │  Agents  │ │  Runs    │ │  Errors  │ │  Avg     │    │
│  │    12    │ │  1,234   │ │   3%     │ │  2.3s    │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                                                            │
│  Agents                                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 🟢 stock.monitor   v2  ✓ active   234 runs   2.1s │  │
│  │ 🟡 football.pred   v1  ⚠ degraded 12 runs    5.4s │  │
│  │ 🔴 scraper.news    v3  ✗ broken   2 runs     0.1s │  │
│  │ ...                                                │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│  Recent Runs                                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 10:42  stock.monitor  v2  NEUTRAL  2.1s   0.85    │  │
│  │ 10:41  stock.monitor  v2  NEUTRAL  1.8s   0.79    │  │
│  │ 10:40  football.pred v1  RISK     5.4s   0.42    │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### Page 2: Agent Detail

```
┌────────────────────────────────────────────────────────────┐
│ ← Back   stock.monitor   v2  (active)         [Diff] [Logs]│
├────────────────────────────────────────────────────────────┤
│  Metadata              │  Verdict Distribution              │
│  Domain: stock         │  ████████████ NEUTRAL   68%        │
│  Created: 2026-06-20   │  ████         POSITIVE  19%        │
│  Runs: 234             │  ███          NEGATIVE  10%        │
│  Avg time: 2.1s        │  ▌            RISK       3%        │
│  Success rate: 97%     │                                   │
│                       │                                   │
│  Versions              │  Latency (last 24h)              │
│  ┌─────────────────┐  │  ▁▂▃▂▁▁▂▃▅▇▆▄▃▂▁                │
│  │ v1 archived     │  │  0────2────4────6────8s          │
│  │ v2 active  ←    │  │                                   │
│  │ v3 testing      │  │                                   │
│  └─────────────────┘  │                                   │
└────────────────────────────────────────────────────────────┘
```

### Page 3: 实时日志（WebSocket）

```
┌────────────────────────────────────────────────────────────┐
│  Live Logs                              [Filter: agent_id] │
├────────────────────────────────────────────────────────────┤
│ 10:42:15.123  INFO   agent=stock.monitor run=r_xyz │ ... │
│ 10:42:15.456  INFO   agent=stock.monitor run=r_xyz │ ... │
│ 10:42:16.012  WARN   agent=stock.monitor run=r_xyz │ ... │
│ 10:42:16.789  INFO   agent=football.pred run=r_abc │ ... │
│ ...                                                        │
│                                              [Pause] [×]  │
└────────────────────────────────────────────────────────────┘
```

---

## 🔌 API 设计

### 页面路由

| Method | Path | 用途 |
|---|---|---|
| GET | `/` | 首页（agent 列表） |
| GET | `/agents/{agent_id}` | agent 详情 |
| GET | `/logs` | 实时日志页 |
| GET | `/metrics` | metrics 仪表盘 |

### REST API（供 HTMX 局部刷新）

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/agents` | 列出所有 agent（JSON） |
| GET | `/api/agents/{id}` | 单个 agent 详情 |
| GET | `/api/agents/{id}/runs?limit=50` | 历史 runs |
| GET | `/api/agents/{id}/versions` | 版本列表 |
| GET | `/api/metrics/summary` | 全局指标 |
| GET | `/api/logs/recent?n=100` | 最近 N 条日志 |

### WebSocket

| Path | 用途 |
|---|---|
| `WS /ws/logs` | 实时日志推送（按 `FORGE_LOG_FILE` 监听） |
| `WS /ws/runs` | 实时新 run 推送（订阅 EventBus） |

---

## 🛠️ 技术栈

### 后端
- **FastAPI** — 异步 web 框架，自动 OpenAPI 文档
- **uvicorn** — ASGI 服务器
- **Jinja2** — 模板引擎
- **Pydantic v2** — 数据校验（已依赖）
- **watchfiles** — 监听日志文件变化

### 前端
- **HTMX 1.9** — HTML over the wire（无构建步骤）
- **Alpine.js 3** — 轻量交互（折叠 / 弹窗）
- **Tailwind CSS CDN** — 样式（Play CDN，无需 build）
- **Chart.js** — 简单的图（verdict 分布、latency）

### 数据
- **JSON 文件** — MANIFEST.json / log file（已存在）
- **内存** — MetricsCollector（已存在）
- **SQLite**（可选）— AgentReport 历史持久化

---

## 📦 依赖

加进 `pyproject.toml` 的 `[project.optional-dependencies]`：

```toml
dashboard = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "jinja2>=3.1",
    "watchfiles>=0.21",
]
```

---

## 🚀 启动方式

```bash
# 1. 安装（带 dashboard 依赖）
pip install "forge-agent[dashboard]"

# 2. 启动（在项目根目录）
cd /path/to/your-project
forge-agent dashboard

# 输出:
#   forge-agent Dashboard
#   → URL: http://localhost:8765
#   → Project: /path/to/your-project
#   → Press Ctrl+C to stop

# 3. 打开浏览器
open http://localhost:8765
```

---

## 📊 阶段化交付（与 Phase 0-3 集成）

### 阶段 1：MVP（1-2 天）—— **可选项**，不影响 Phase 1 启动

| 任务 | 估时 |
|---|---|
| D1.1 FastAPI app 骨架 | 2h |
| D1.2 页面 1：Agent 列表（静态） | 2h |
| D1.3 REST API 读 MANIFEST.json | 1h |
| D1.4 Tailwind + HTMX 美化 | 2h |
| D1.5 `forge-agent dashboard` CLI 命令 | 1h |
| **合计** | **1.5 天** |

### 阶段 2：交互（2-3 天）

| 任务 | 估时 |
|---|---|
| D2.1 页面 2：Agent 详情（含 version diff） | 1d |
| D2.2 实时日志 WebSocket | 1d |
| D2.3 Metrics 面板（接 MetricsCollector） | 0.5d |

### 阶段 3：高级（1 周）

| 任务 | 估时 |
|---|---|
| D3.1 AgentReport 历史持久化（SQLite） | 1d |
| D3.2 Trace 详情（observe→decide→act 耗时） | 1d |
| D3.3 多租户 / 鉴权 | 1d |
| D3.4 Docker 镜像发布 | 1d |
| D3.5 react 升级（SPA） | 2d |

---

## 🧪 测试策略

- **单元测试**：`test_dashboard_app.py`（API 路由、模板渲染）
- **集成测试**：`test_dashboard_e2e.py`（启动 → 访问 → 看到 agent）
- **E2E 测试**：playwright/selenium（可选）

---

## 🎯 决策点

### 立即决策（影响 D1.x）
- [x] 技术栈：FastAPI + Jinja2 + HTMX（你已选）
- [x] 范围：完整架构 / MVP 起步（我建议）
- [ ] 数据持久化：MVP 用 JSON / 升级用 SQLite？

### 后续决策（影响 D2.x+）
- [ ] 多租户：单用户本地版 / 支持多团队？
- [ ] 鉴权：本地无 / token 鉴权 / OAuth？
- [ ] 部署：本地 / Docker / K8s？

---

## 📚 参考资料

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [HTMX 文档](https://htmx.org/)
- [Tailwind Play CDN](https://tailwindcss.com/docs/installation/play-cdn)
- [LangSmith Dashboard](https://docs.smith.langchain.com/) — 灵感来源
- [Weights & Biases](https://wandb.ai/) — 灵感来源

---

## 🔄 与现有模块的集成

| 现有模块 | 集成方式 |
|---|---|
| `generator/manifest.py` | `data/manifest.py` 读 MANIFEST.json |
| `observability/logger.py` | `data/logs.py` tail log file（FORGE_LOG_FILE=1）|
| `observability/metrics.py` | `data/metrics.py` 包一层，暴露 API |
| `observability/events.py` | `routes/ws.py` 订阅 EventBus |
| `cli/__init__.py` | 加 `cmd_dashboard.py` |

---

**下一步**：创建任务卡 `D1.1` - `D1.5`，等 Phase 0 / Phase 1 启动后并行推进。
