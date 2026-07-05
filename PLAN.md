# forge-agent 实施计划

> **版本**：v4
> **最后更新**：2026-07-03
> **本文件是唯一执行入口**（取代 `ROADMAP.md` 任务跟踪、`docs/tasks/STATUS.md` 日常更新）

---

## 一、产品定义

### 一句话

**用户自建 Agent，再从已有 Agent 中组装 Pipeline，运行并查看结果。**

### 核心模型（只有三个概念）

```text
Project
  │
  ├── Agent          用户自己创建的智能体（可复用）
  │     └── 配置：prompt、工具、输出格式、mock/真实模式
  │
  ├── Pipeline       从 Agent 库中勾选成员，定义编排方式
  │     └── 配置：agent 列表、并行/串行、Chief 汇总
  │
  └── Run            每次 Pipeline 执行产生一条记录
        └── 内容：各 Agent 报告 + Chief 决策 + 输入 payload
```

### 用户旅程

```text
1. 启动平台          forge-agent up
2. 创建 Agent A      选模板 → 填参数 → 保存
3. 创建 Agent B      同上（可不同配置）
4. 创建 Pipeline     勾选 A、B → Chief 选 generic.chief → 保存
5. 运行 Pipeline     填 payload（如 {"keyword": "labubu"}）→ Run
6. 查看结果          运行历史 → 各 Agent 报告 + Chief 汇总
```

### 设计原则

| 原则 | 说明 |
|------|------|
| **Agent 与 Pipeline 解耦** | 同一 Agent 可被多个 Pipeline 引用 |
| **Web 优先** | 主路径在浏览器；CLI/TUI 给开发者 |
| **模板降认知** | scraper/analyzer 等只是「建 Agent 时的预设」，不是产品术语 |
| **mock 默认可用** | 无 API Key 也能跑通；真实 LLM/工具可切换 |
| **部署后自助** | 长远目标：一套服务、多租户、用户自己建 Agent/Pipeline |

### 明确不做（当前阶段）

- 自然语言建 Pipeline（P4.4 `architect` 高级入口，默认规则+Mock）
- `forge-agent generate` 写 Python（开发者能力，非主路径）
- Skill 市场 / SaaS 计费（P3 以后）

---

## 二、架构映射

```text
┌─────────────────────────────────────────────────────────┐
│  Web UI（forge-agent up）                                │
│  /agents/new  /pipelines/new  /pipelines/{id}/run       │
├─────────────────────────────────────────────────────────┤
│  REST API          pages.py + api.py                    │
├─────────────────────────────────────────────────────────┤
│  存储（LocalTenant）                                      │
│  agents/*.yaml     pipelines/*.yaml     state/*.json   │
├─────────────────────────────────────────────────────────┤
│  运行时                                                   │
│  launcher → AgentFactory → TeamRunner → ChiefAgent       │
└─────────────────────────────────────────────────────────┘
```

### Agent 文件结构（用户自建产物）

```yaml
# agents/weibo_analyst.yaml
agents:
  - agent_id: weibo_analyst
    name: 微博分析
    template: prompt_agent
    config:
      mock_mode: true
      prompt: "分析 {platform} 上 {keyword} 的趋势…"
      tools: [weibo.hot_search]          # 可选
      variables: { keyword: keyword, platform: platform }
      output_schema: { verdict: str, confidence: float, ... }
      output_mapping: { verdict: verdict, ... }
      mock_response: '{"verdict": "lean_positive", ...}'
```

### Pipeline 文件结构（用户组装产物）

```yaml
# pipelines/trend.yaml
pipeline_id: trend
name: 趋势分析
team:
  team_id: trend_team
  agent_ids: [weibo_analyst, xhs_analyst]   # 用户勾选的 Agent
  chief_id: generic.chief                   # 内置汇总 Agent
  mode: parallel
```

---

## 三、现状评估

| 能力 | 状态 | 位置 |
|------|------|------|
| Web 创建/编辑/删除 Agent | ✅ | `web/routes/api.py`, `create_agent.html` |
| Web 创建/编辑/删除 Pipeline | ✅ | `create_pipeline.html` |
| Web 运行 + 历史 | ✅ | `run_pipeline.html`, `runs.html` |
| Agent 类型模板（表单预设） | ✅ | `builtin/agent_types/` |
| Chief 汇总 | ✅ | `builtin/chief_agent.py` |
| 多租户文件隔离 | ✅ | `platform/local_tenant.py` |
| 运行结果持久化 | ✅ | `project/state_store.py` |
| Docker 部署 | ✅ | `Dockerfile`, `docker-compose.yml` |

| 缺口 | 影响 |
|------|------|
| Web 无多项目/多租户切换 | 部署多人用时需 Phase 2 |
| 无登录鉴权 | 公网部署需 Phase 2 |
| 手动验收未做 | 需本地 `forge-agent up` 走一遍黄金路径 |

---

## 四、执行阶段

### Phase 0 — 跑通主路径 ✅

**目标**：`forge-agent up` → 建 Agent → 建 Pipeline → 运行 → 看历史，全程 mock。

| ID | 任务 | 验收 | 状态 |
|----|------|------|------|
| P0.1 | Pipeline 表单默认 Chief = `generic.chief` | 新建 Pipeline 页默认选中 | ✅ |
| P0.2 | launcher 运行前注册 `generic.chief` | `_ensure_builtin_agents()` | ✅ |
| P0.3 | 修复 `_configure_llm` 使用项目所属 tenant 根目录 | 临时目录项目可运行 | ✅ |
| P0.4 | Web 全流程集成测试 | `pytest tests/integration/test_web_e2e.py` 全绿 | ✅ |
| P0.5 | README Quick Start 对齐主路径 | 文档以 up → Agent → Pipeline 为准 | ✅ |
| P0.6 | 手动走一遍黄金路径 | 按下方脚本操作成功 | 🟡 自动化已覆盖，待人工 UI 确认 |

**黄金路径验收脚本**：

```bash
forge-agent up
# http://localhost:8787

# 1. + Agent → scraper → weibo_analyst（keyword/platform/tool）
# 2. + Agent → scraper → xhs_analyst
# 3. + Pipeline → 勾选两个 Agent → Chief 保持 generic.chief
# 4. 运行 → payload: {"keyword": "labubu"}
# 5. 运行历史 → 看到 2 份 Agent 报告 + Chief 汇总
```

**Phase 0 出口**：`pytest tests/integration/test_web_e2e.py::TestWebGoldenPath::test_p06_golden_path_script` + 下方手动脚本（或 `scripts/golden_path_check.sh`）。

---

### Phase 1 — Agent / Pipeline 体验（约 1 周）

**目标**：让「自建 Agent → 组装 Pipeline」更好用，UI 语言统一。

| ID | 任务 | 验收 | 状态 |
|----|------|------|------|
| P1.1 | UI 文案：Agent / Pipeline / 运行 | 导航与页面统一中文术语 | ✅ |
| P1.2 | 空项目引导 | 首页三步引导 + 预设快捷入口 | ✅ |
| P1.3 | Agent 模板标签 | scraper→数据抓取 等 | ✅ |
| P1.4 | Agent 快捷编辑 | mock / prompt / tools | ✅ |
| P1.5 | Pipeline 已选摘要 + Chief 说明 | 创建页实时摘要 | ✅ |
| P1.6 | 动态 payload 表单 | 按 Agent variables 生成 | ✅ |
| P1.7 | 结构化结果页 | verdict / evidence / Chief | ✅ |
| P1.8 | Agent 预设库 | 微博/小红书/得物一键创建 | ✅ |

---

### Phase 2 — 部署与多租户（约 1～2 周）

**目标**：部署一套服务，多个租户各自建 Agent/Pipeline。

| ID | 任务 | 验收 |
|----|------|------|
| P2.1 | Web 路由 `/t/{tenant}/p/{project}/...` | 一套 up 服务多租户 | ✅ |
| P2.2 | Web 内新建/切换/列出 Project | 无需 CLI `forge-agent new` | ✅ |
| P2.3 | 用户注册 → 自动创建 tenant | 新用户有独立命名空间 | ✅ |
| P2.4 | 登录 + Session；只能访问自己 tenant | 跨 tenant 返回 403 | ✅ |
| P2.5 | docker-compose volume 持久化数据 | 重启不丢 Agent/Pipeline | ✅ |
| P2.6 | 部署文档：环境变量、端口、数据目录 | 外人能独立部署 | ✅ |

---

### Phase 3 — 运行可观测与真实数据（按需）

| ID | 任务 | 验收 |
|----|------|------|
| P3.1 | 每次 Run 写入 trace_id + logs | `logs/{trace_id}.json` | ✅ |
| P3.2 | Web 运行详情展示 Trace | 各 Agent 耗时、输入输出 | ✅ |
| P3.3 | 租户级 LLM 配置 UI | Web 填 API Key | ✅ |
| P3.4 | 工具层：scraper_agent + 真实/降级 mock 工具 | 可切换真实数据 | ✅ |
| P3.5 | E2E：注册 → 建 Agent → 建 Pipeline → 运行 | CI 全绿 | ✅ |

---

### Phase 4 — 生态与商业化

| ID | 任务 | 验收 | 状态 |
|----|------|------|------|
| P4.1 | Agent/Pipeline Bundle 导入导出 + 模板市场页 | Web 一键导入/导出/发布共享 | ✅ |
| P4.2 | Pipeline 模板扩展 | 四平台预设 + YAML Bundle 导入 | ✅ |
| P4.3 | DBTenant + 配额 | 企业 SaaS | ⬜ |
| P4.4 | 自然语言建 Pipeline | architect 高级入口 | ✅ |

---

## 五、执行顺序总览

```text
Phase 0  跑通 ✅（待手动验收）
    │
Phase 1  体验 ✅
    │
Phase 2  部署（多租户、登录、Project CRUD）  ← ✅ 已完成
    │
Phase 3  可观测 + 真实数据  ← Phase 3 基本完成（P3.4 ✅）
    │
Phase 4  生态（模板市场 + 智能创建）  ← P4.1/P4.2/P4.4 ✅
```

**当前 focus**：**Agent Generator** — 见 [`AGENT_PLAN.md`](AGENT_PLAN.md) Phase 1（A1.1–A1.6）。Pipeline / 市场 / P4.3 冻结。

---

## 六、验收总入口（Phase 0～2 完成后）

```bash
# 管理员
docker compose up -d

# 用户 A（浏览器）
# 注册 → 新建项目 → 创建 Agent × N → 创建 Pipeline → 运行 → 查看历史

# 用户 B
# 注册 → 完全看不到 A 的 Agent/Pipeline/Run

# 开发者（可选）
forge-agent new myproj --template config-driven --tenant acme
```

---

## 七、进度跟踪

| Phase | 进度 | 状态 |
|-------|------|------|
| Phase 0 跑通 | 6/6 | ✅ 完成 |
| Phase 1 体验 | 8/8 | ✅ 完成 |
| Phase 2 部署 | 6/6 | ✅ 完成 |
| Phase 3 可观测 | 5/5 | ✅ 完成 |
| Phase 4 生态 | 3/4 | 🟡 P4.3 按需 |

---

## 八、决策记录

### 2026-07-03 — 产品模型定稿

- **核心**：用户自建 Agent → 从 Agent 组装 Pipeline → 运行
- **不做为主路径**：generate 写代码、Intent 自动生成、Skill 市场
- **Agent 类型**：降为「创建模板」，不对用户强调 scraper/analyzer/chief
- **Chief**：内置 `generic.chief`，Pipeline 默认选中

### 2026-07-04 — 本地优先策略

- 登录注册（P2.3/P2.4）通过 `FORGE_AGENT_WEB_AUTH=1` 按需开启；默认关闭，本地单机免登录
- 真实 LLM（P3.3/P3.4）按需；默认 Mock 演示
- 优先打磨本地 UI：Mock 提示、运行进度、Trace 时间线

### 2026-07-03 — 执行策略

- Phase 0 必须 mock 跑通，不依赖 API Key
- Phase 1 再打磨 UI/体验
- Phase 2 再做多租户与登录
- 垂直场景（社媒趋势）作为 Agent/Pipeline **模板**，不是平台边界

---

## 九、任务提交规范

完成 tasks 时在 commit message 引用 ID：

```text
feat(P0.3): use project tenant root in launcher LLM config
test(P0.4): fix web golden path e2e
docs(P0.5): align README with Agent/Pipeline flow
```

每完成一项：更新本节「进度跟踪」表。
