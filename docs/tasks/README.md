# forge-agent 实施路径（入口）

> **这是项目实施的唯一入口。从这里开始。**

---

## 🚀 5 分钟理解项目

| 文档 | 作用 |
|---|---|
| [STATUS.md](./STATUS.md) | **总进度跟踪**（唯一真相源） |
| [phase-0-overview.md](./phase-0-overview.md) | Phase 0 任务总览（当前阶段） |

---

## 📋 任务卡片清单

### Phase 0 — 打地基（当前阶段 🔴）

| ID | 任务 | 状态 | 估时 |
|---|---|---|---|
| [T0.1](./T0.1-python-env.md) | Python 3.10+ 真环境 | ⬜ | 30min |
| [T0.2](./T0.2-license.md) | LICENSE 文件 | ⬜ | 5min |
| [T0.3](./T0.3-changelog.md) | CHANGELOG.md | ⬜ | 30min |
| [T0.4](./T0.4-ci.md) | GitHub Actions CI | ⬜ | 2h |
| [T0.5](./T0.5-precommit.md) | pre-commit 配置 | ⬜ | 30min |
| [T0.6](./T0.6-e2e-smoke.md) | 端到端冒烟测试 | ⬜ | 1h |

### Phase 1 — 验核心假设（待开始）

| ID | 任务 | 状态 | 估时 |
|---|---|---|---|
| T1.1 | OpenAI 真实 provider 跑通 | ⬜ | 2h |
| T1.2 | 生成代码 Validator 强化 | ⬜ | 1d |
| T1.3 | 沙箱真隔离 | ⬜ | 1d |
| T1.4 | 端到端测试套件（10 个领域） | ⬜ | 1.5d |
| T1.5 | 失败回滚 + 二次重试 | ⬜ | 1d |

### Phase 2 — 兑现差异化（待开始）

| 任务 | 状态 | 估时 |
|---|---|---|
| 2.1 Agent 类型化（5 个核心 type） | ⬜ | 1 周 |
| 2.2 Dataset 模块（爬虫核心） | ⬜ | 0.5 周 |
| 2.3 MCP 真接通（filesystem + 1 个） | ⬜ | 0.5 周 |
| 2.4 自迭代闭环（evolve → v2） | ⬜ | 0.3 周 |

### Phase 3 — 生态 + 体验（待开始）

| 任务 | 状态 | 估时 |
|---|---|---|
| 3.1 mkdocs 文档站 | ⬜ | 1d |
| 3.2 forge-agent new 模板（4 个） | ⬜ | 1.5d |
| 3.3 错误信息友好化 | ⬜ | 4h |
| 3.4 Pydantic 校验 | ⬜ | 4h |
| 3.5 OpenTelemetry 集成 | ⬜ | 4h |
| 3.6 forge-agent doctor | ⬜ | 4h |
| 3.7 真实 demo 视频 | ⬜ | 4h |
| 3.8 PyPI 发布 | ⬜ | 4h |

### Dashboard MVP — 观测后台（可与 Phase 0/1 并行）

| ID | 任务 | 状态 | 估时 |
|---|---|---|---|
| [D1.1](./D1.1-fastapi-skeleton.md) | FastAPI app 骨架 | ⬜ | 2h |
| [D1.2](./D1.2-agent-list-page.md) | 页面 1：Agent 列表 | ⬜ | 2h |
| [D1.3](./D1.3-manifest-api.md) | REST API 读 MANIFEST | ⬜ | 1h |
| [D1.4](./D1.4-htmx-tailwind.md) | Tailwind + HTMX 美化 | ⬜ | 2h |
| [D1.5](./D1.5-dashboard-cli.md) | `forge-agent dashboard` CLI | ⬜ | 1h |

详见 [dashboard-overview.md](./dashboard-overview.md) 与 [architecture/dashboard.md](../architecture/dashboard.md)。

---

## 🎯 立即开始

**第 1 步**：看 [STATUS.md](./STATUS.md) 了解当前进度
**第 2 步**：跑 `bash scripts/check_phase0.sh` 看自动化检查结果
**第 3 步**：按 [phase-0-overview.md](./phase-0-overview.md) 顺序执行
**第 4 步**：完成一个任务 → 更新 STATUS.md + 任务卡的"执行记录"段 → git commit

---

## 🤖 自动化检查

```bash
# Phase 0 全部 6 项检查
bash scripts/check_phase0.sh

# Dashboard MVP 全部 5 项检查
bash scripts/check_dashboard.sh

# 端到端冒烟
bash scripts/smoke_test.sh

# 启动 Dashboard
forge-agent dashboard
# → http://localhost:8765

# 跑所有测试
pytest
```

---

## 📊 铁律

1. **每个任务都有验证标准** — 没标准 = 没做完
2. **完成一个 → 更新 STATUS.md → git commit** — 不积压
3. **每周日更新周报** — 同步进度
4. **每个 Phase 完成后 review** — 不连续跨 Phase
5. **Phase 1 跑不通则全项目重评** — 不带病进入 Phase 2

---

## 📁 文件结构

```
docs/tasks/
├── README.md                    # 本文件（入口）
├── STATUS.md                    # 总进度跟踪
├── phase-0-overview.md          # Phase 0 总览
├── T0.1-python-env.md           # Phase 0 任务卡 (6 张)
├── T0.2-license.md
├── T0.3-changelog.md
├── T0.4-ci.md
├── T0.5-precommit.md
├── T0.6-e2e-smoke.md
└── ...

scripts/
├── check_phase0.sh              # Phase 0 自动化检查
├── smoke_test.sh                # 端到端冒烟
├── check_phase1.sh              # Phase 1 检查（待创建）
└── ...
```

---

**当前状态**：Phase 0 入口，0/6 完成
**下一步**：执行 T0.1
