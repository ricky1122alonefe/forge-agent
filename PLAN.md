# forge-agent 实施计划 v2

> **最后更新**：2026-07-03
> **取代**：`docs/tasks/STATUS.md`（引擎建设跟踪，已完成）+ `ROADMAP.md`（战略草稿，部分过时）
> **本文件是后续开发的唯一入口**

---

## 一、你想做的东西（产品定义）

### 一句话

**多租户、低代码的「社媒趋势情报」平台**——用户输入关键词/IP，系统自动从多个平台抓取数据、并行分析、汇总决策，输出可执行的趋势研判报告。

### 不是

- 不是通用 Python Agent 代码生成器（那是底层能力，不是产品）
- 不是单一平台的爬虫脚本
- 不是需要用户写代码的框架

### 是

- 部署一套系统，每个租户拥有自己的 projects / agents / pipelines
- 用户通过 **Web UI 或 TUI** 配置和运行，不写代码
- 典型场景：潮玩 IP 热度、品牌舆情、商品趋势（微博 / 小红书 / 得物 / 抖音）
- 架构同时支持 **本地单点** 和未来的 **企业 SaaS**

### 核心用户旅程

```text
1. forge-agent new labubu_watch --tenant acme --template trend-analysis
2. forge-agent up --tenant-id acme --project-id labubu_watch
3. 浏览器里：选平台 → 填关键词 → 一键运行
4. 看到：各平台专家报告 + Chief 汇总决策 + 历史记录
```

### 核心数据流

```text
                    ┌─────────────────────────────────────┐
  keyword/IP ──────►│  scraper agents（并行）              │
                    │  微博 / 小红书 / 得物 / 抖音          │
                    └──────────────┬──────────────────────┘
                                   │ 结构化数据
                    ┌──────────────▼──────────────────────┐
                    │  analyzer（可选，深度分析）            │
                    └──────────────┬──────────────────────┘
                                   │ agent reports
                    ┌──────────────▼──────────────────────┐
                    │  chief（汇总决策）                     │
                    │  verdict / confidence / risk / action │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  state/ + logs/ + Web UI 展示        │
                    └─────────────────────────────────────┘
```

### 标准输出（所有 agent 统一）

```json
{
  "verdict": "lean_positive | lean_neutral | lean_negative | risk",
  "confidence": 0.82,
  "risk": 0.15,
  "evidence": ["..."],
  "recommended_action": "execute | watch | hold | alert",
  "metrics": {}
}
```

---

## 二、现状诊断

### 已完成（不用再建）

| 模块 | 状态 | 位置 |
|------|------|------|
| Agent 核心引擎 | ✅ | `core/`, `pipeline/`, `llm/` |
| 多租户隔离 | ✅ | `platform/local_tenant.py` |
| Agent 类型库 | ✅ | `builtin/agent_types/` (scraper/analyzer/chief) |
| TUI 交互配置 | ✅ | `project/tui.py`, `project/launcher.py` |
| Web UI 骨架 | ✅ | `web/`, `forge-agent up` |
| 运行结果存储 | ✅ | `project/state_store.py` |
| LLM 多租户配置 | ✅ | `platform/llm_config.py` |
| YAML 校验 | ✅ | `platform/config_validator.py` |
| 趋势 demo 原型 | ✅ | `examples/toy_trend_demo/` |

### 核心问题：两条线没有接通

```text
  examples/toy_trend_demo/          src/forge_agent/builtin/
  ─────────────────────────         ──────────────────────────
  ✅ 真实 scraper（Playwright）      ❌ placeholder 返回假数据
  ✅ scraper_agent 模板              ❌ 只有 prompt_agent
  ✅ architect 自然语言建 pipeline   ❌ 只能 TUI 手动选类型
  ✅ 完整 trend 配置                 ❌ 没有 trend-analysis 模板
         │                                    │
         └────────── 没有合并 ────────────────┘
```

**结论**：引擎和平台壳子都有了，但产品 demo 跑在 `examples/` 里，主路径还是 mock。**下一步不是加新抽象，是把 demo 能力并入主路径。**

---

## 三、实施阶段

### Sprint 1 — 接通真实数据层（P0，约 1 周）

**目标**：`forge-agent up` 跑出来的结果，和 `toy_trend_demo` 一样有真实数据结构（mock 可切换）。

| ID | 任务 | 验收标准 |
|----|------|----------|
| S1.1 | 把 `examples/toy_trend_demo/scrapers/` 迁入 `builtin/scrapers/` | 模块可独立 import，测试通过 |
| S1.2 | 把 `builtin/tools/social.py` 的 placeholder 替换为真实 scraper 调用 | `weibo.hot_search` 在无 Playwright 时 graceful fallback 到 mock |
| S1.3 | 注册 `scraper_agent` 模板到主路径 | `AgentFactory` 在 launcher 启动时自动注册 |
| S1.4 | 更新 `scraper.yaml` agent 类型，对齐 toy_trend_demo 的 config 字段 | TUI/Web 创建的 scraper agent 能真正调工具 |
| S1.5 | 补集成测试：`scraper → chief` 端到端（mock 模式） | `pytest tests/integration/test_trend_pipeline.py` 通过 |

**出口命令**：

```bash
forge-agent new trend_demo --tenant acme --template trend-analysis
cd ~/.forge-agent/tenants/acme/projects/trend_demo
python run.py --pipeline trend --payload '{"keyword": "labubu"}'
# 输出各平台 verdict + chief 汇总，data_source 字段标明 mock/real
```

---

### Sprint 2 — 趋势分析开箱模板（P0，约 3 天）

**目标**：新用户 3 分钟内跑通完整 demo，不需要手动建 agent。

| ID | 任务 | 验收标准 |
|----|------|----------|
| S2.1 | 新增 `--template trend-analysis` | 自动生成 agents（微博/小红书/得物）+ pipeline + chief |
| S2.2 | 默认 `mock_mode: true`，README 说明如何切换真实模式 | 无 API key 也能跑通 |
| S2.3 | 把 `architect.py` 的核心逻辑迁入 `project/architect.py` | `python run.py --architect "分析 labubu 在微博的热度"` 自动生成 pipeline |
| S2.4 | Web UI 加「一键运行趋势分析」入口 | 填 keyword → 看到结果页 |

**出口命令**：

```bash
forge-agent new labubu --tenant acme --template trend-analysis
forge-agent up --tenant-id acme --project-id labubu
# 浏览器填 labubu → Run → 看到报告
```

---

### Sprint 3 — 可观测性闭环（P1，约 3 天）

**目标**：每次运行可追溯、可复盘（ROADMAP 6.5）。

| ID | 任务 | 验收标准 |
|----|------|----------|
| S3.1 | `launcher._run_pipeline()` 集成 `TraceStore` | 运行后 `logs/{trace_id}.json` 存在 |
| S3.2 | `RunRecord` 写入 `trace_id` | `python run.py --list` 显示 trace 关联 |
| S3.3 | Web UI 运行详情页展示 trace（各 agent 耗时、输入输出） | 点击 run → 看到 span 列表 |
| S3.4 | 结构化 JSON 日志写入 `tenant/.../logs/forge-agent.log` | 日志按租户/项目隔离 |

---

### Sprint 4 — 产品质量门禁（P1，约 1 周）

**目标**：主路径有测试兜底，CI 绿色。

| ID | 任务 | 验收标准 |
|----|------|----------|
| S4.1 | 多租户 E2E：`new → create → run → list`（临时目录） | 不污染 `~/.forge-agent` |
| S4.2 | 多租户隔离测试：acme/bob 同名项目结果不互覆盖 | 已有部分测试，补全 |
| S4.3 | Web API 集成测试（agent CRUD + run） | TestClient 覆盖 |
| S4.4 | 修复 dashboard 测试 collection error | `pytest` 全绿 |
| S4.5 | `pre-commit run --all-files` + CI 流水线 | PR 自动跑 lint + test |

---

### Sprint 5 — 交付与文档（P2，约 3 天）

**目标**：外人能独立安装、理解、使用。

| ID | 任务 | 验收标准 |
|----|------|----------|
| S5.1 | 更新 README Quick Start 为 trend-analysis 路径 | 新用户按 README 能跑通 |
| S5.2 | 录制 demo 视频或 GIF（T3.7） | 展示 keyword → 多平台报告 → chief 决策 |
| S5.3 | `docker compose up` 验证 | 容器内 `forge-agent up` 可用 |
| S5.4 | mkdocs 加「趋势分析」产品章节 | 文档站反映真实产品定位 |

---

### Sprint 6+ — 未来（暂不做，记下来）

| 方向 | 内容 | 触发条件 |
|------|------|----------|
| 自然语言建 pipeline | architect 增强 + 工具自动发现 | Sprint 2 完成后用户反馈需要 |
| Skill 市场 | `social-scraper-skill` 可安装包 | 有 2+ 垂直场景时 |
| 真实 SaaS | DBTenant + REST API + 鉴权 + 配额 | 有企业客户需求时 |
| 更多平台 | 抖音真实 scraper、淘宝、B站 | 按业务优先级逐个加 |
| React SPA | 替换 HTMX | Web UI 功能稳定后再考虑 |

---

## 四、执行顺序（总览）

```text
Sprint 1  接通真实数据层          ← 现在从这里开始
    │
Sprint 2  trend-analysis 模板
    │
    ├─→ Sprint 3  可观测性
    │
    └─→ Sprint 4  测试门禁
            │
        Sprint 5  交付文档
            │
        Sprint 6+  SaaS / 生态（按需）
```

**原则**：

1. **先通主路径，再加功能** — 一条命令跑通 > 十个半成品模块
2. **mock 默认可用，真实可切换** — demo 不依赖 API key / Playwright
3. **不重复造轮子** — 从 `examples/toy_trend_demo/` 迁移，不重写
4. **每个 Sprint 有出口命令** — 可演示、可验证

---

## 五、验收总入口

全部 Sprint 1-5 完成后，应能完成：

```bash
# 1. 安装
bash scripts/install.sh
forge-agent doctor

# 2. 创建趋势分析项目
forge-agent new labubu_watch --tenant acme --template trend-analysis

# 3. Web UI 运行
forge-agent up --tenant-id acme --project-id labubu_watch
# → 浏览器输入 labubu → 一键运行 → 看到 3 平台报告 + Chief 决策

# 4. CLI 运行（等价）
cd ~/.forge-agent/tenants/acme/projects/labubu_watch
python run.py --pipeline trend --payload '{"keyword": "labubu"}'

# 5. 查看历史
python run.py --list

# 6. 自然语言建 pipeline（Sprint 2）
python run.py --architect "分析 dimoo 在小红书和得物的热度"

# 7. 切换真实数据（可选）
# 编辑 agents/*.yaml mock_mode: false，安装 playwright
```

---

## 六、进度跟踪

| Sprint | 状态 | 开始 | 完成 |
|--------|------|------|------|
| S1 接通真实数据层 | ⬜ | — | — |
| S2 trend-analysis 模板 | ⬜ | — | — |
| S3 可观测性 | ⬜ | — | — |
| S4 测试门禁 | ⬜ | — | — |
| S5 交付文档 | ⬜ | — | — |

> 每完成一个任务：更新上表 + 在对应 commit message 里引用任务 ID（如 `feat(S1.2): wire real scrapers into builtin tools`）

---

## 七、关键决策记录

### 2026-07-03 — 产品定位收敛

- **决策**：forge-agent 的产品形态是「社媒趋势情报平台」，不是通用 Agent 工厂
- **理由**：`toy_trend_demo` 是唯一跑通真实业务逻辑的 demo；builtin placeholder 无法演示价值
- **影响**：优先合并 demo 到主路径；`forge-agent generate` 降级为高级/开发者功能
- **放弃**：短期内不做 React SPA、不做 Skill 市场、不做 SaaS 计费

### 2026-07-03 — 计划文档整合

- **决策**：`PLAN.md` 取代 `docs/tasks/` 和 `ROADMAP.md` 作为执行入口
- **理由**：旧 plan 跟踪引擎建设（98% 完成），新 plan 跟踪产品交付
- **保留**：`ROADMAP.md` 作战略参考，不再逐条维护 checkbox
