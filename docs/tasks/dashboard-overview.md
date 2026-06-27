# Dashboard — 实施路径

> **目标**：本地 web 面板，让用户"看见" agent 的运行
> **总估时**：阶段 1（MVP）1.5 天 + 阶段 2（交互）3 天 + 阶段 3（高级）1 周
> **架构**：FastAPI + Jinja2 + HTMX（Python 优先，无构建步骤）
> **最后更新**：2026-06-27

---

## 任务状态总览

| ID | 任务 | 阶段 | 估时 | 依赖 | 状态 |
|---|---|---|---|---|---|
| [D1.1](./D1.1-fastapi-skeleton.md) | FastAPI app 骨架 | MVP | 2h | Phase 0 | ⬜ |
| [D1.2](./D1.2-agent-list-page.md) | 页面 1：Agent 列表（静态） | MVP | 2h | D1.1 | ⬜ |
| [D1.3](./D1.3-manifest-api.md) | REST API 读 MANIFEST.json | MVP | 1h | D1.1 | ⬜ |
| [D1.4](./D1.4-htmx-tailwind.md) | Tailwind + HTMX 美化 | MVP | 2h | D1.2 | ⬜ |
| [D1.5](./D1.5-dashboard-cli.md) | `forge-agent dashboard` CLI | MVP | 1h | D1.4 | ⬜ |
| [D2.1](./D2.1-agent-detail.md) | 页面 2：Agent 详情 | 交互 | 1d | D1.5 | ⬜ |
| [D2.2](./D2.2-ws-logs.md) | 实时日志 WebSocket | 交互 | 1d | D1.5 | ⬜ |
| [D2.3](./D2.3-metrics-panel.md) | Metrics 面板 | 交互 | 0.5d | D1.5 | ⬜ |
| [D3.1](./D3.1-sqlite-runs.md) | AgentReport 历史 SQLite | 高级 | 1d | D2.1 | ⬜ |
| [D3.2](./D3.2-trace.md) | Trace 详情 | 高级 | 1d | D3.1 | ⬜ |
| [D3.3](./D3.3-auth.md) | 多租户 / 鉴权 | 高级 | 1d | D3.1 | ⬜ |
| [D3.4](./D3.4-docker.md) | Docker 镜像 | 高级 | 1d | D3.1 | ⬜ |
| [D3.5](./D3.5-react-spa.md) | React SPA 升级 | 高级 | 2d | D3.2 | ⬜ |

**图例**：⬜ 未开始 · 🟡 进行中 · ✅ 已完成 · ❌ 失败

---

## 执行顺序

```
Phase 0 / Phase 1 推进中
        │
        ├─→ D1.1 FastAPI app 骨架
        │       │
        │       ├─→ D1.2 Agent 列表页（静态）
        │       │       │
        │       │       └─→ D1.4 HTMX/Tailwind 美化
        │       │               │
        │       │               └─→ D1.5 forge-agent dashboard CLI
        │       │                       │
        │       └─→ D1.3 REST API ─────┤
        │                               │
        │                               ├─→ D2.1 Agent 详情
        │                               ├─→ D2.2 WebSocket 实时日志
        │                               └─→ D2.3 Metrics 面板
        │                                       │
        │                                       └─→ D3.x 高级
```

---

## MVP 出口标准（D1.1 - D1.5 全部完成）

- [ ] `pip install "forge-agent[dashboard]"` 干净通过
- [ ] `forge-agent dashboard` 命令可启动
- [ ] 浏览器访问 `http://localhost:8765` 看到 agent 列表
- [ ] 列表展示 agent_id / version / active 状态 / 描述
- [ ] UI 干净（Tailwind 风格）
- [ ] 关闭后无残留进程

---

## 当前进度

- ⬜ D1.1 FastAPI app 骨架
- ⬜ D1.2 页面 1：Agent 列表（静态）
- ⬜ D1.3 REST API 读 MANIFEST.json
- ⬜ D1.4 Tailwind + HTMX 美化
- ⬜ D1.5 `forge-agent dashboard` CLI
- ⬜ D2.1 页面 2：Agent 详情
- ⬜ D2.2 实时日志 WebSocket
- ⬜ D2.3 Metrics 面板
- ⬜ D3.x 高级功能

**下一步**：执行 D1.1（FastAPI app 骨架）

---

## 与 Roadmap 的集成

- **Phase 0 / Phase 1**：并行推进 D1.1 - D1.5（MVP）
- **Phase 2.4 自迭代闭环**：完成后立即做 D2.1（用 Dashboard 看 evolve 效果）
- **Phase 3.1 mkdocs 文档站**：加 Dashboard 章节
- **Phase 3.7 Demo 视频**：Dashboard 是 demo 的核心展示

---

## 依赖添加

`pyproject.toml` 需要加：

```toml
[project.optional-dependencies]
dashboard = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "jinja2>=3.1",
    "watchfiles>=0.21",
]
all = [
    "forge-agent[llm,mcp,search,otel,dashboard]",
]
```

执行 D1.1 时同时修改 pyproject.toml。

---

## 决策点（执行前确认）

- [x] 技术栈：FastAPI + Jinja2 + HTMX（你已选）
- [x] 范围：MVP 起步，架构完整
- [ ] 数据持久化：MVP 用 JSON / 升级用 SQLite？
- [ ] 默认端口：8765 / 8000 / 其他？

---

## 参考

- [架构设计文档](../architecture/dashboard.md)
- [HTMX 官方](https://htmx.org/)
- [FastAPI 官方](https://fastapi.tiangolo.com/)
- [Tailwind Play CDN](https://tailwindcss.com/docs/installation/play-cdn)
