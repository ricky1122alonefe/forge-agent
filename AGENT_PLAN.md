# Agent Generator 实施计划

> **版本**：v1
> **最后更新**：2026-07-05
> **优先级**：最高 — 冻结 Pipeline / 市场 / P4.3，全部精力在此
> **取代**：此前 Phase 4 周边工作的 focus

---

## 一、北极星目标

**一句话**：用户描述需求 → 系统生成**可 Mock 运行、可验收、可复用**的 Agent YAML，覆盖 **≥90% 常见 Agent 形态**。

### 量化验收（最终出口）

| 指标 | 标准 |
|------|------|
| 场景矩阵 | 20 条代表场景，Mock 下 **≥18 条** 生成 + 运行通过 |
| 生成路径 | NL / 表单 / preset → **同一条 AgentSpec 内核** |
| 零 API Key | 规则路径生成 + `mock_cases` 自动 smoke |
| Agent 资产 | 可导出 Bundle、跨 Project 导入、带 version |

### 明确不做（本计划内）

- 画布 Workflow 编辑器（Dify / Flowise  territory）
- 完整 RAG 平台（后置可选）
- `forge-agent generate` 写 Python 作为主路径
- Pipeline / 模板市场新功能

---

## 二、产品定位

```text
市面平台：Workflow / App 是一等公民
forge-agent：Agent 是一等公民，Pipeline 只是组装
```

**创新组合**（借鉴开源优点）：

| 借鉴 | 我们怎么做 |
|------|-----------|
| CrewAI YAML 声明式 | `AgentSpec` 为标准中间格式 |
| Dify 工具目录 | Tool Registry 元数据 + 自动匹配 |
| Agno 结构化输出 | schema profile 驱动生成 |
| Dify Evaluation | 每 Agent 自带 `mock_cases` |
| 自研 Mock 阶梯 | draft → verified → connected → production |

---

## 三、Agent 原语（5 个够拼 90%）

| 原语 | 模板 | 用途 |
|------|------|------|
| **Fetcher** | `scraper_agent` | 调工具/API 取数 |
| **Searcher** | `search_agent` | 搜索 → 分析 |
| **Reasoner** | `prompt_agent` | 纯 LLM + 自定义 schema |
| **Synthesizer** | `prompt_agent` | 读 upstream `{reports}` 汇总 |
| **Monitor** | `prompt_agent` | 阈值 / 告警型输出 |

Chief = 内置 `generic.chief`，非用户创建 Agent。

---

## 四、AgentSpec 数据结构

```yaml
agents:
  - agent_id: weibo_analyst
    name: 微博趋势分析
    domain: generic
    template: scraper_agent
    primitive: fetcher          # 生成器元数据
    tags: [generated]
    config:
      mock_mode: true
      platform: weibo
      tools: [weibo.hot_search]
      prompt: "..."
      output_schema: {...}
      output_mapping: {...}
      variables:
        keyword: keyword
    mock_cases:                 # 生成即测
      - name: default
        input: { keyword: labubu }
        expect_keys: [verdict, confidence]
```

---

## 五、执行阶段

### Phase 1 — 统一内核 + 数据流（当前）

**目标**：一条生成链路 + 3 类原语 Mock 跑通

| ID | 任务 | 验收 |
|----|------|------|
| A1.1 | `agent_spec/` 模块：`AgentSpec`、`AgentSpecGenerator`、`write_agent_yaml` | 单元测试通过 |
| A1.2 | `mock_cases` 校验 + smoke runner | 给定 spec 自动跑 mock |
| A1.3 | Sequential 模式 upstream `reports` 注入 | Synthesizer Agent Mock 跑通 |
| A1.4 | `search` agent_type YAML + Searcher 原语 | Web/CLI 可创建 |
| A1.5 | API：`POST /api/agent-spec/plan` + `/apply` | E2E 1 条 |
| A1.6 | 场景矩阵前 3 条 golden case | 测试全绿 |

**Phase 1 三条 golden case**：

1. **Fetcher**：分析 labubu 微博热度 → `scraper_agent` + weibo tool
2. **Searcher**：搜索 AI 行业动态并总结 → `search_agent`
3. **Synthesizer**：汇总上游两份报告 → `prompt_agent` + `{reports}`

---

### Phase 2 — 五原语 + 动态 Schema

| ID | 任务 | 验收 |
|----|------|------|
| A2.1 | `monitor` / `generator` agent_type + schema profiles | 矩阵 +4 条 |
| A2.2 | Tool Registry 元数据（description, params, platforms） | 生成器自动选 tool |
| A2.3 | `AgentTypeRegistry` 租户扩展 + 生成器读取 | 自定义 type 可生成 |
| A2.4 | NL 增强（LLM 解析 AgentSpec，失败降级规则） | 无 Key 仍可用 |
| A2.5 | 场景矩阵达到 20 条，≥18 绿 | 90% 出口 |

---

### Phase 3 — 产品化与成熟度

| ID | 任务 | 验收 |
|----|------|------|
| A3.1 | Web「生成 Agent」页（预览 Spec → 应用） | 替代 scattered 入口 |
| A3.2 | Agent 成熟度阶梯 UI（mock → real） | 设置页可见 |
| A3.3 | Agent Bundle 含 mock_cases | 市场导入可自测 |
| A3.4 | `architect` 改为调用 AgentSpecGenerator | 不再硬编码 trend |

---

### Phase 4 — 类型扩展与 LLM 增强

| ID | 任务 | 验收 |
|----|------|------|
| A4.1 | `reasoner` agent_type + schema_profile 参数 | Registry 可生成 |
| A4.2 | Web LLM planner 接入 `generate_spec` / architect | 有 Key 时 llm_assisted |
| A4.3 | 场景矩阵覆盖率报告 API | `/agent-spec/coverage` ≥18/20 |
| A4.4 | architect UI 对齐 AgentSpec | 显示原语/Schema + 跳转生成页 |

---

## 六、场景矩阵（20 条，Phase 2 出口）

### 抓取 / 搜索（8）
- [x] 社媒关键词 trend（微博） — S01
- [x] 多平台 trend（微博+小红书） — S02
- [x] 竞品价格监控 — S03
- [x] 新闻摘要 — S04
- [x] API 拉数分析 — S05
- [x] 网页内容抽取 — S06
- [x] 搜索问答 — S07
- [x] RSS/Feed 摘要 — S08

### 分析 / 推理（7）
- [x] 情感分类 — S09
- [x] 风险评级 — S10
- [x] 长文摘要 — S11
- [x] 实体抽取 — S12
- [x] 表格对比 — S13
- [x] 报告润色 — S14
- [x] 多文档综合（Synthesizer） — S15

### 监控 / 动作（5）
- [x] 阈值告警 — S16
- [x] 同比异常 — S17
- [x] 规则黑白名单 — S18
- [x] 条件 execute/watch/hold — S19
- [x] 结构化建议输出 — S20

Phase 2 出口：**20/20 Mock smoke 全绿**（`tests/scenarios/test_scenario_matrix.py`）

---

## 七、架构

```text
Requirement (NL / form / preset_id)
        │
        ▼
AgentSpecGenerator ──► AgentSpec (validate)
        │                      │
        │                      ├── mock_cases smoke
        ▼                      ▼
   agent_builder         agents/{id}.yaml
   (from_spec)                 │
                                ▼
                          AgentFactory.load
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            run_single_agent          TeamRunner.run
            (Agent 试跑 A6)           (Pipeline 组装)
```

**代码位置**：

| 模块 | 路径 |
|------|------|
| AgentSpec 内核 | `src/forge_agent/agent_spec/` |
| Agent 类型 | `src/forge_agent/builtin/agent_types/` |
| 运行时模板 | `src/forge_agent/core/templates/` |
| Web API | `src/forge_agent/web/routes/api.py` |
| 测试 | `tests/unit/agent_spec/`, `tests/scenarios/` |

---

## 八、进度跟踪

| Phase | 进度 | 状态 |
|-------|------|------|
| Phase 1 内核 + 数据流 | 6/6 | ✅ |
| Phase 2 五原语 + 矩阵 | 5/5 | ✅ |
| Phase 3 产品化 | 4/4 | ✅ |
| Phase 4 类型 + LLM | 4/4 | ✅ |
| Phase 5 租户类型 + 统一路径 | 4/4 | ✅ |
| Phase 6 Agent 试跑 | 3/3 | ✅ |
| Phase 7 成熟度闭环 | 4/4 | ✅ |
| Phase 8 Agent 资产 version | 4/4 | ✅ |
| Phase 9 自动连线 + 能力可配 | 5/5 | ✅ |

**当前 focus**：Phase 9 已完成 — primitive 自动连线编队 + memory/constraints 能力可配

**执行纪律**：新 work 必须先写入本文档 Phase 表再开发；禁止 Pipeline / 市场 / CLI 支线。

---

### Phase 9 — 自动连线 + 能力可配

| ID | 任务 | 验收 |
|----|------|------|
| A9.1 | `wire.py` primitive 插头表 + `validate_wiring()` | Synthesizer 无前游报错 |
| A9.2 | `compose.py` 规则拆解 → 多 AgentSpec + pipeline 建议 | golden：双 Fetcher + Synth |
| A9.3 | `POST /agent-spec/compose` + apply agents+pipeline + Web 编队 Tab | Mock smoke 全绿 |
| A9.4 | `capabilities.py` memory/constraints → AgentSpec config | 关键词触发、默认 memory 关 |
| A9.5 | agent_type 可选 `capabilities` 模板 | from-type 继承 |

---

### Phase 8 — Agent 资产 version + Generator 质量

| ID | 任务 | 验收 |
|----|------|------|
| A8.1 | `_meta.spec_version` / `revision` / `generated_at` on apply | overwrite 递增 revision |
| A8.2 | profile-aware `expect_keys` in mock_cases | 分析类含 verdict/confidence/risk/evidence/recommended_action |
| A8.3 | `validate_agent_asset()` + `GET /api/agents/{id}/validate` | 缺 version 报错 |
| A8.4 | Bundle export 携带 agent_revision | 单元测试 + 矩阵仍 20/20 |

---

### Phase 7 — 成熟度阶梯闭环（计划 §二 Mock 阶梯）

| ID | 任务 | 验收 |
|----|------|------|
| A7.1 | `mark_real_run_verified` 写 `_meta` | 真实试跑后持久化 |
| A7.2 | 非 Mock 试跑前 `ensure_llm_ready` | 无 Key 明确报错 |
| A7.3 | `compute_maturity` 需 `real_run_verified` 才进 connected/production | 单元测试 |
| A7.4 | 试跑 API 返回 `maturity`；详情页刷新阶梯 | E2E |

---

### Phase 6 — Agent 一等公民：单独运行

| ID | 任务 | 验收 |
|----|------|------|
| A6.1 | `run_single_agent` + `POST /agents/{id}/run` | Mock 下返回 report |
| A6.2 | 默认 payload 来自 mock_cases | `/run-defaults` |
| A6.3 | Agent 详情页「试跑」UI | 无需 Pipeline 可看结果 |

---

### Phase 5 — 租户类型与统一生成路径

| ID | 任务 | 验收 |
|----|------|------|
| A5.1 | 修复 `shared/agent_types/` 路径 + Registry source | 租户类型可加载 |
| A5.2 | 租户 agent_type CRUD API | POST/DELETE `/api/agent-types` |
| A5.3 | `/agent-spec/from-type` + create/preset 走 AgentSpec | 含 mock_cases smoke |
| A5.4 | Web 类型管理页 + 生成页「从类型」Tab | `/agent-types` + E2E |

---

## 九、任务提交规范

```text
feat(A1.1): add AgentSpec models and generator kernel
fix(A1.3): inject upstream reports in sequential team runs
test(A1.6): golden cases for fetcher searcher synthesizer
```

每完成一项：更新本节「进度跟踪」表。
