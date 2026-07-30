# forge-agent 实施计划

> **版本**：v5（大改造基线）
> **最后更新**：2026-07-27
> **定位**：通用 Agent 编排平台 — 生成即测、Judge 护航、任务托管、IM 触达
> **本文件是唯一执行入口**（取代 ROADMAP.md 任务跟踪、AGENT_PLAN.md focus）

---

## 一、产品定位

### 一句话

**自托管的多 Agent 编排平台：用户自建 Agent → 组装 Pipeline → 托管运行 → IM 触达。**

### 与市面方案的差异化

| 市面痛点 | forge-agent 解法 |
|---------|-----------------|
| 生成完即裸奔，质量无保障 | AgentSpec 生成 → mock smoke → Judge 评分 → 失败自愈（最多3轮） |
| Agent 绑死 Workflow | Agent 一等公民，Pipeline 只是组装，跨 Pipeline 复用 |
| 平台与框架割裂 | Web UI 自助 + AgentSpec 声明式内核 + 代码生成，低代码与代码可滑动 |
| 只能手动同步跑 | runtime 任务托管：异步/持久/重试/定时/恢复 |
| 触达不了真实用户 | integrations/im：飞书/钉钉/企微/Slack 入站触发 + 出站推送 |
| 多专家协作无结构 | AgentReport/AgentBoard 契约 + Chief 汇总 + Judge 校准 |

### 明确不做（本阶段）

- 画布 Workflow 编辑器（Dify/Flowise territory）
- 完整 RAG 平台（后置可选）
- SaaS 计费 / 多租户配额（后置）

---

## 二、能力栈

```
┌─────────────────────────────────────────┐
│  IM 适配层   飞书/钉钉/企微/Slack        │  触达 + 触发（入站/出站）
├─────────────────────────────────────────┤
│  任务托管层   队列/状态/重试/回调/定时    │  持久运行
├─────────────────────────────────────────┤
│  Pipeline 引擎  DAG/串并行/Chief         │  编排
├─────────────────────────────────────────┤
│  Agent 运行时  BaseAgent/Factory         │  执行
└─────────────────────────────────────────┘
```

下两层（Pipeline/Agent）已具备；上两层（runtime/integrations）为本轮大改造新增的基础能力。

---

## 三、目标架构

```text
forge-agent/
├── core/                  内核：纯契约与抽象（无业务逻辑）
│   ├── agent.py           BaseAgent 生命周期 hook（瘦身）
│   ├── contracts.py       AgentReport / AgentBoard / AgentContext
│   ├── enums.py           Action / Verdict / AgentStatus
│   └── capabilities.py    能力协议（search/memory/reflect/log）
│
├── spec/                  AgentSpec 内核（原 agent_spec/ 收敛）
│   ├── models.py          数据模型
│   ├── generator.py       生成器（策略注册表，6 primitive 合并）
│   ├── compose.py         编队（原 compose+wire）
│   ├── ci.py              CI 门禁（原 ci+chain_smoke+smoke）
│   ├── repair.py          自愈（原 repair+maturity+coverage）
│   ├── versioning.py      版本
│   └── profiles/          原语 + schema 配置
│
├── judge/                 质量评估
│   ├── models.py          IssueSeverity/JudgeIssue/DimensionScore/JudgeReport
│   ├── checkers.py        各 check_*（独立可测）
│   └── judge.py           Judge 类
│
├── runtime/               【新层】任务托管
│   ├── models.py          TaskRun 状态机
│   ├── store.py           持久化（复用 SQLite）
│   ├── runner.py          异步 worker
│   ├── retry.py           重试策略（指数退避）
│   ├── triggers.py        触发源 manual/schedule/webhook/im
│   └── scheduler.py       cron 定时
│
├── pipeline/              编排引擎
│   ├── engine.py          DAG 执行
│   ├── aggregator.py      Board 汇总
│   └── chief.py           ChiefAgent（含 guardrails/prompt 拆分）
│
├── tools/                 统一工具层
│   ├── registry.py        工具注册中心
│   ├── mcp.py             MCP 客户端
│   ├── scraper.py         抓取
│   ├── search.py          搜索
│   └── builtin/           示例工具（标注非必需）
│
├── integrations/          【新层】外部集成
│   ├── im/
│   │   ├── base.py        IMAdapter 协议
│   │   ├── feishu.py      飞书
│   │   ├── dingtalk.py    钉钉
│   │   ├── wecom.py       企业微信
│   │   ├── slack.py       Slack
│   │   ├── formatter.py   AgentReport → IM 卡片
│   │   └── router.py      入站事件 → 触发 Pipeline
│   └── webhook/
│       └── receiver.py    通用 webhook 入口
│
├── learning/              复盘成长（与 judge 边界清晰）
├── storage/               统一存储（ForgeStore + SQLite 底座）
├── llm/                   LLM 层（多 provider + 密钥 + usage）
├── platform/              多租户 + 项目隔离
├── web/                   单一 Web 服务
│   ├── app.py             唯一 FastAPI app
│   ├── auth/              认证
│   ├── routes/
│   │   ├── agents.py      /agents/*
│   │   ├── pipelines.py   /pipelines/*
│   │   ├── runs.py        /runs/* （任务托管 API）
│   │   ├── spec.py        /agent-spec/*
│   │   ├── llm.py         /llm/*
│   │   ├── bundles.py     /bundles/*
│   │   └── integrations.py /integrations/* （IM/webhook 配置）
│   ├── observability/     Trace/Metrics（原 dashboard/ 合并）
│   ├── templates/
│   └── static/
├── cli/                   CLI（瘦身）
└── templates/             项目模板（去垂直化，多领域）
```

---

## 四、迁移决策矩阵

| 操作 | 对象 | 理由 |
|------|------|------|
| 保留 | core 契约、spec 内核、judge、pipeline 引擎、llm、platform、storage 底座、Bundle | 核心资产 |
| 合并 | `dashboard/` → `web/observability/` | 两套 app.py 重叠 |
| 合并 | `generator/` → `spec/` | 代码生成是 Spec 生成的重模式 |
| 合并 | `builtin/tools`+`mcp/`+`scraper/`+`search/` → `tools/` | 统一工具层 |
| 合并 | `agent_spec/` 16模块 → `spec/` 7模块 | ci/smoke/chain_smoke 合一；compose/wire 合一；repair/maturity/coverage 合一 |
| 移动 | `builtin/chief_agent.py` → `pipeline/chief.py` | Chief 是编排组件，拆 guardrails/prompt |
| 移动 | `project/state_store.py` → `runtime/store.py` | 结果持久化归运行时 |
| 移动 | `scheduler/` → `runtime/`（降级为执行组件） | 托管引擎含执行策略 |
| 瘦身 | `core/base.py` | trace→装饰器；constraint→回 constraints；evolve→回 learning |
| 删除 | 垂直硬编码（chief 足球文案、社媒门面） | 通用框架不该有 |
| 新增 | `runtime/` 任务托管 | 基础能力缺口 |
| 新增 | `integrations/im/` + `webhook/` | IM 协作基础能力缺口 |

---

## 五、执行阶段（按依赖顺序）

### S1 — 架构骨架

**目标**：建 runtime/ + integrations/ 空骨架，定义接口契约，不破坏现有功能。

| ID | 任务 | 验收 |
|----|------|------|
| S1.1 | 建 `runtime/` 模块骨架：models/store/runner/retry/triggers/scheduler 空文件 + 接口定义 | import 不报错 |
| S1.2 | 建 `integrations/im/` + `webhook/` 骨架：base 协议 + 空 adapter | IMAdapter 协议可被 mock 实现 |
| S1.3 | 定义 TaskRun 状态机：pending→running→succeeded/failed/cancelled/retrying | 单元测试覆盖状态流转 |

### S2 — 收拢合并

**目标**：消除重复抽象，统一模块边界。每步保测试绿。

| ID | 任务 | 验收 |
|----|------|------|
| S2.1 | `dashboard/` 合并进 `web/observability/`，删除独立 app.py | 单一 web 服务，观测路由可访问 |
| S2.2 | `generator/` 合并进 `spec/`，收敛为一条生成路径 | 生成功能不丢，单一生成入口 |
| S2.3 | `builtin/tools`+`mcp/`+`scraper/`+`search/` → `tools/` | 统一工具注册，旧 import 兼容 |
| S2.4 | `agent_spec/` 16模块 → `spec/` 7模块（ci/smoke/chain_smoke 合并等） | 场景矩阵 20/20 仍绿 |
| S2.5 | `builtin/chief_agent.py` → `pipeline/chief.py`，拆 GuardRailEngine + ChiefPrompts | Chief 功能不变，可独立测试 guardrails |
| S2.6 | `project/state_store.py` → `runtime/store.py` | 运行结果持久化迁移 |
| S2.7 | `scheduler/` 降级为 `runtime/` 内部执行组件 | 现有 pipeline 执行不破 |

### S3 — 任务托管实装

**目标**：runtime/ 从骨架变成可用引擎。

| ID | 任务 | 验收 |
|----|------|------|
| S3.1 | `task_runs` 表 + 持久化（复用 SQLite） | run 记录重启不丢 |
| S3.2 | 异步 runner：提交即返回 run_id，后台执行 | `POST /runs` 不阻塞 |
| S3.3 | 状态查询 API：`GET /runs/{id}` | 返回 status/进度/结果 |
| S3.4 | 重试策略：指数退避 + max_attempts | 失败自动重试，记录 attempts |
| S3.5 | 定时触发：cron 表达式 → 周期创建 run | 定时 pipeline 自动跑 |
| S3.6 | 恢复：重启扫描 running 态 → 标记 interrupted | 重启不丢运行态 |
| S3.7 | 回调机制：完成触发 webhook | 回调可被 IM 订阅 |

### S4 — Web 接线

**目标**：拆 api.py，runs API 接 runtime，观测合并。

| ID | 任务 | 验收 |
|----|------|------|
| S4.1 | 拆 `web/routes/api.py`（1165行）→ agents/pipelines/runs/spec/llm/bundles/integrations | 原文件仅留 router 聚合 |
| S4.2 | `/runs` API 接 runtime 层 | 异步提交 + 状态查询可用 |
| S4.3 | 观测页（原 dashboard）合并进 web，展示 task_run 状态/Trace | 单一服务内可见 |
| S4.4 | Agent 卡片首屏展示 Judge 分 + 成熟度阶梯 | 质量门禁招牌化 |

### S5 — IM 适配

**目标**：integrations/im 实装，飞书优先，接 runtime。

| ID | 任务 | 验收 |
|----|------|------|
| S5.1 | IMAdapter 协议 + 飞书 adapter（入站事件 + 出站消息） | 飞书机器人可收发 |
| S5.2 | im/router：入站 @机器人/命令 → 触发 Pipeline → 创建 task_run | IM 里 `/run trend` 能触发 |
| S5.3 | im/formatter：AgentReport → 飞书卡片 | 结果推送可读 |
| S5.4 | 出站回调：task_run 完成 → 推送 IM | 运行完自动回 IM |
| S5.5 | 钉钉/企微/Slack adapter（同协议） | 至少再接 1 个 |

### S6 — 核心瘦身

**目标**：解耦 base.py，去垂直残留。

| ID | 任务 | 验收 |
|----|------|------|
| S6.1 | `core/base.py` trace 逻辑 → RunTracer 装饰器/mixin | base.py < 300 行 |
| S6.2 | constraint 逻辑移回 `constraints/` | base 不含 constraint |
| S6.3 | evolve 编排移回 `learning/`，base 只留 hook | base 不含 learning 编排 |
| S6.4 | `judge/__init__.py` 拆 models/checkers/judge | __init__ 仅 re-export |
| S6.5 | 删除 chief 足球硬编码文案 → config 注入 | 通用 Chief 无领域残留 |
| S6.6 | 统一术语：agent_type/template/primitive 收敛为统一词汇表 | 全局命名一致 |

### S7 — 去垂直化

**目标**：消除"社媒工具"体感，证明通用性。

| ID | 任务 | 验收 |
|----|------|------|
| S7.1 | 新增非社媒模板：文档摘要 / 客服路由 / 数据监控告警 | 3 个通用模板可用 |
| S7.2 | 社媒预设降级为"示例模板"，标注非必需 | 不再当门面 |
| S7.3 | README/首页改为通用场景 | 无社媒/体育痕迹 |
| S7.4 | 真实 LLM + 真实 MCP 工具端到端黄金路径 | 非 Mock 跑通一条 |

---

## 六、执行顺序总览

```text
S1 架构骨架   建 runtime/ + integrations/ 接口
    ↓
S2 收拢合并   dashboard→web、generator→spec、工具合并、agent_spec 收敛
    ↓
S3 任务托管   runtime 实装（状态机+持久化+异步+重试+定时）
    ↓
S4 Web 接线   拆 api.py，runs API，观测合并
    ↓
S5 IM 适配    飞书优先，接 runtime trigger/callback
    ↓
S6 核心瘦身   base.py 解耦、chief 拆解、judge 拆分
    ↓
S7 去垂直化   模板/示例/门面通用化
```

**依赖关系**：runtime（S3）必须先于 IM（S5），因为 IM 的 trigger/callback 依赖 runtime 接口。其余阶段顺序执行，每阶段保测试绿。

---

## 七、进度跟踪

| 阶段 | 进度 | 状态 |
|------|------|------|
| S1 架构骨架 | 3/3 | ✅ |
| S2 收拢合并 | 7/7 | ✅ done |
| S3 任务托管 | 7/7 | ✅ done |
| S4 Web 接线 | 4/4 | ✅ done |
| S5 IM 适配 | 0/5 | ⬜ |
| S6 核心瘦身 | 0/6 | ⬜ |
| S7 去垂直化 | 0/4 | ⬜ |

---

## 八、决策记录

### 2026-07-27 — 方向重定义（v5）

- **定位**：通用 Agent 编排平台，不绑定任何垂直领域，与 guess_you_like 无关
- **接受大范围改造**：用户授权架构级重构，非打补丁
- **保留核心资产**：AgentSpec + Judge + 自愈 + CI 门禁 + BaseAgent 契约
- **新增基础能力**：runtime 任务托管 + integrations/im（市面基础能力，非高级功能）
- **消除技术债**：上帝文件拆分、重复抽象合并、过度设计收敛、垂直残留清除

### 2026-07-27 — 能力栈定稿

- 四层栈：IM 适配 → 任务托管 → Pipeline 引擎 → Agent 运行时
- 下两层已有，上两层本轮补齐
- runtime 先于 IM，IM 通过 runtime 的 trigger/callback 接入，不侵入核心

---

## 九、任务提交规范

```text
refactor(S2.1): merge dashboard into web/observability
feat(S3.2): async run submission returns run_id
feat(S5.2): im router triggers pipeline from bot command
chore(S7.3): de-verticalize README to generic scenarios
```

每完成一项：更新第七节「进度跟踪」表。
