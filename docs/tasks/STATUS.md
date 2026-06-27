# forge-agent 项目进度跟踪

> **本文件是项目进度的唯一真相源（Single Source of Truth）**
> **每次完成任务后，更新本文件 + 对应任务卡的"执行记录"段**
> **最后更新**：2026-06-27

---

## 总体进度

```
Phase 0 (打地基)     [██████████] 6/6    (100%) ✅
Phase 1 (验核心假设) [██████████] 5/5    (100%) ✅
Phase 2 (兑现差异化) [█░░░░░░░░░] 1/15   (7%)   🟡
Phase 3 (生态体验)   [░░░░░░░░░░] 0/8    (0%)
Dashboard MVP        [░░░░░░░░░░] 0/5    (0%)  ← 放一放
Dashboard 交互       [░░░░░░░░░░] 0/3    (0%)  ← 放一放
Dashboard 高级       [░░░░░░░░░░] 0/5    (0%)  ← 放一放
─────────────────────────────────────────
总进度               [████░░░░░░] 12/47  (26%)
```

---

## Phase 0 — 打地基

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T0.1 | Python 3.10+ 真环境 | ✅ | 2026-06-27 10:35 | `python --version` ≥ 3.10 | 3.14.3 |
| T0.2 | LICENSE 文件 | ✅ | 已有 | `test -f LICENSE && grep MIT LICENSE` | OK |
| T0.3 | CHANGELOG.md | ✅ | 2026-06-27 10:40 | `test -f CHANGELOG.md && grep "0.3.0"` | OK |
| T0.4 | GitHub Actions CI | ✅ | 2026-06-27 10:42 | `test -f .github/workflows/test.yml` | OK |
| T0.5 | pre-commit 配置 | ✅ | 2026-06-27 10:42 | `test -f .pre-commit-config.yaml` | OK |
| T0.6 | 端到端冒烟测试 | ✅ | 2026-06-27 10:45 | `bash scripts/smoke_test.sh` | PASS |

**Phase 0 检查**：`bash scripts/check_phase0.sh`

---

## Phase 1 — 验核心假设

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T1.1 | DeepSeek 真实 provider 跑通 | ✅ | 2026-06-27 10:44 | `forge-agent generate ... --provider=deepseek` | ✅ generate + run |
| T1.2 | 生成代码 Validator 强化 | ✅ | 2026-06-27 10:55 | `pytest tests/unit/test_validator.py` | 14/14 |
| T1.3 | 沙箱真隔离 | ✅ | 2026-06-27 11:15 | `pytest tests/unit/test_sandbox.py` | 20/20 |
| T1.4 | 端到端测试套件 | ✅ | 2026-06-27 11:25 | `pytest tests/e2e/test_generation_e2e.py` | 13/13 (skip without key) |
| T1.5 | 失败回滚 + 二次重试 | ✅ | 2026-06-27 11:35 | `pytest tests/unit/test_retry.py` | 23/23 |

**T1.1 状态详情**：
- ✅ DeepSeek API 连通性验证
- ✅ generate 命令成功（"monitor stock prices" → 生成可用代码）
- ✅ 生成代码使用真实 LLM 调用（`from forge_agent.llm import chat`）
- ✅ 验证通过（`validation_status: passed`）
- ⬜ 加载 + 运行 agent 验证（待 T1.4 端到端测试）

**Phase 1 检查**：`bash scripts/check_phase1.sh`

---

## Phase 2 — 兑现差异化

### 2.1 Agent 类型化

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T2.1.1 | AgentType 枚举 | ✅ | 2026-06-27 11:45 | `pytest tests/unit/test_agent_type.py` | 35/35 |
| T2.1.2 | AgentRequirements 加字段 | ✅ | 2026-06-27 11:50 | `pytest tests/unit/test_requirements.py` | 24/24 |
| T2.1.3 | prompts.py 按 type 分流 | ✅ | 2026-06-27 11:55 | `pytest tests/unit/test_prompts.py` | 22/22 |
| T2.1.4 | CodeGenerator 按 type 选模板 | ✅ | 2026-06-27 11:58 | `pytest tests/unit/test_templates.py` | 21/21 |
| T2.1.5 | forge-agent list 显示 type | ⬜ | — | `forge-agent list` | — |

### 2.2 Dataset 模块

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T2.2.1 | Dataset dataclass | ⬜ | — | `pytest tests/unit/test_dataset.py` | — |
| T2.2.2 | LocalDatasetStore + SqliteDatasetStore | ⬜ | — | `pytest tests/unit/test_dataset_store.py` | — |
| T2.2.3 | datasets/registry.py | ⬜ | — | `pytest tests/unit/test_dataset_registry.py` | — |
| T2.2.4 | 生成器 prompt 加 dataset | ⬜ | — | `pytest tests/integration/test_scraper_with_dataset.py` | — |
| T2.2.5 | forge-agent datasets CLI | ⬜ | — | `forge-agent datasets list` | — |

### 2.3 MCP 真接通

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T2.3.1 | 接入 mcp 官方 SDK | ⬜ | — | `pytest tests/unit/test_mcp_client.py` | — |
| T2.3.2 | 接 1 个真实 MCP server | ⬜ | — | `pytest tests/integration/test_mcp_filesystem.py` | — |
| T2.3.3 | forge-agent mcp CLI | ⬜ | — | `forge-agent mcp list-tools` | — |
| T2.3.4 | 生成器支持 mcp_tools | ⬜ | — | `pytest tests/integration/test_mcp_generation.py` | — |

### 2.4 自迭代闭环

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T2.4.1 | learning/optimizer.py 真实现 | ⬜ | — | `pytest tests/unit/test_optimizer.py` | — |
| T2.4.2 | evolve() 方法从 stub 变真 | ⬜ | — | `pytest tests/integration/test_evolve.py` | — |

**Phase 2 检查**：`bash scripts/check_phase2.sh`

---

## Phase 3 — 生态 + 体验

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| T3.1 | mkdocs 文档站 | ⬜ | — | `mkdocs build --strict` | — |
| T3.2 | forge-agent new 模板完整化 | ⬜ | — | `bash scripts/test_all_templates.sh` | — |
| T3.3 | 错误信息友好化 | ⬜ | — | `pytest tests/unit/test_error_messages.py` | — |
| T3.4 | JSON Schema / Pydantic 校验 | ⬜ | — | `pytest tests/unit/test_pydantic_validation.py` | — |
| T3.5 | OpenTelemetry 集成 | ⬜ | — | `pytest tests/integration/test_otel.py` | — |
| T3.6 | forge-agent doctor 命令 | ⬜ | — | `forge-agent doctor` | — |
| T3.7 | 真实 demo 视频 | ⬜ | — | (人工验证) | — |
| T3.8 | PyPI 发布准备 | ⬜ | — | `python -m build` | — |

**Phase 3 检查**：`bash scripts/check_phase3.sh`

---

## Dashboard MVP — 观测后台

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| D1.1 | FastAPI app 骨架 | ⬜ | — | `pytest tests/unit/dashboard/test_app.py` | — |
| D1.2 | 页面 1：Agent 列表（静态） | ⬜ | — | `pytest tests/unit/dashboard/test_pages.py` | — |
| D1.3 | REST API 读 MANIFEST.json | ⬜ | — | `pytest tests/unit/dashboard/test_api.py` | — |
| D1.4 | Tailwind + HTMX 美化 | ⬜ | — | `pytest tests/unit/dashboard/test_visual.py` | — |
| D1.5 | `forge-agent dashboard` CLI | ⬜ | — | `bash scripts/check_dashboard.sh` | — |

## Dashboard 交互

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| D2.1 | 页面 2：Agent 详情 | ⬜ | — | `pytest tests/unit/dashboard/test_detail.py` | — |
| D2.2 | 实时日志 WebSocket | ⬜ | — | `pytest tests/integration/test_ws_logs.py` | — |
| D2.3 | Metrics 面板 | ⬜ | — | `pytest tests/unit/dashboard/test_metrics_panel.py` | — |

## Dashboard 高级

| ID | 任务 | 状态 | 完成时间 | 验证命令 | 通过 |
|---|---|---|---|---|---|
| D3.1 | AgentReport 历史 SQLite | ⬜ | — | `pytest tests/integration/test_sqlite_runs.py` | — |
| D3.2 | Trace 详情 | ⬜ | — | `pytest tests/integration/test_trace.py` | — |
| D3.3 | 多租户 / 鉴权 | ⬜ | — | `pytest tests/integration/test_auth.py` | — |
| D3.4 | Docker 镜像 | ⬜ | — | `docker build -t forge-agent .` | — |
| D3.5 | React SPA 升级 | ⬜ | — | (人工验证) | — |

**Dashboard 检查**：`bash scripts/check_dashboard.sh`

---

## 状态图例

- ⬜ 未开始
- 🟡 进行中
- ✅ 已完成（带完成时间和验证记录）
- ❌ 失败（带失败原因）

---

## 周报

### Week 1 (2026-06-27 ~ 2026-07-03)

**目标**：完成 Phase 0

**实际**：⬜ 0/6 完成

**阻塞**：（待填）

**下周计划**：（待填）

---

## 决策记录

### 2026-06-27

- **决策 1**：使用 structlog + contextvars 作为统一日志方案
  - 理由：原生 JSON 输出，async/task 隔离
  - 影响：Phase 0 增加 `bind_context` / `configure_logging` API
  - 实施状态：✅ 已完成（v0.3.0）

- **决策 2**：动态生成 agent 不入 git，靠 CodeStore + MANIFEST
  - 理由：服务器上生成，git 装不下
  - 影响：所有生成代码本地落盘，审计靠 MANIFEST.json
  - 实施状态：✅ 已完成（v0.2.0）

- **决策 3**：分 4 Phase 实施，每个 Phase 独立验证
  - 理由：避免"做完了发现假设错误"
  - 影响：所有任务卡分阶段，每个 Phase 都有"出口标准"
  - 实施状态：🟡 进行中（Phase 0）

---

## 测试统计

| 阶段 | 测试数 | 通过 | 失败 |
|---|---|---|---|
| v0.1 | 16 | 16 | 0 |
| v0.2 | 40 | 40 | 0 |
| v0.3 | 59 | 59 | 0 |
| Phase 0 | TBD | TBD | TBD |
| Phase 1 | TBD | TBD | TBD |
| Phase 2 | TBD | TBD | TBD |
| Phase 3 | TBD | TBD | TBD |

---

## 自动化命令一览

```bash
# 查看当前 Phase 0 状态
bash scripts/check_phase0.sh

# 跑端到端冒烟
bash scripts/smoke_test.sh

# 检查 Dashboard MVP
bash scripts/check_dashboard.sh

# 启动 Dashboard
forge-agent dashboard  # http://localhost:8765

# 跑所有测试
pytest

# 跑特定 Phase 的测试
pytest tests/e2e/  # e2e
pytest tests/integration/  # integration
pytest tests/unit/  # unit

# 跑带覆盖率
pytest --cov=forge_agent --cov-report=term-missing
```

---

## 维护说明

1. **每次完成任务**：
   - 在本文件更新状态（⬜ → ✅）
   - 在任务卡的"执行记录"段追加记录
   - 跑对应的验证命令
   - git commit

2. **每周日晚上**：
   - 更新"周报"段
   - 同步实际进度 vs 计划

3. **遇到阻塞**：
   - 在"决策记录"段记录
   - 更新"下周计划"

4. **里程碑达成**：
   - 在"测试统计"段记录
   - 庆祝 🎉
