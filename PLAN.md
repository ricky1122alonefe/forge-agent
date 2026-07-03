# forge-agent 实施计划 v2.1

> **最后更新**：2026-07-03
> **产品定位**：部署后，用户通过多租户隔离，**自己在 Web 里创建 Agent 和 Pipeline**
> **本文件是后续开发的唯一入口**

---

## 一、产品定义

### 一句话

**可部署的多租户 Agent 编排平台**——管理员部署一套 forge-agent，每个租户/用户登录后，在浏览器里自己创建智能体、组装 Pipeline、运行并查看结果，无需写代码。

### 核心用户旅程

```text
管理员：
  docker compose up          # 或 forge-agent up
  → 平台运行在 http://host:8787

租户用户（第一次）：
  注册/登录 → 创建或加入租户 → 新建项目
  → 选 Agent 类型 → 填参数 → 保存
  → 选多个 Agent 组成 Pipeline → 指定 Chief → 保存
  → 填运行参数 → Run → 查看报告和历史

租户用户（日常使用）：
  登录 → 切换项目 → 运行已有 Pipeline → 查看历史/Trace
```

### 架构模型

```text
forge-agent 实例（一套部署）
└── 租户 A（tenant_id: acme）
    ├── 项目 trend_watch
    │   ├── agents/*.yaml      ← 用户自己创建
    │   ├── pipelines/*.yaml   ← 用户自己组装
    │   ├── state/             ← 运行结果（隔离）
    │   └── logs/              ← 执行日志（隔离）
    └── 项目 stock_monitor
        └── ...

└── 租户 B（tenant_id: bob）
    └── 项目 my_pipeline
        └── ...（与 acme 完全隔离）
```

### 设计原则

1. **部署一次，多租户自用** — 不是每个用户装一套 CLI
2. **Web 优先** — 创建/编辑/运行/查看全在浏览器完成；CLI/TUI 留给开发者
3. **YAML 驱动，不写代码** — Agent 类型模板 + 表单填参 → 生成 `agents/*.yaml`
4. **数据严格隔离** — 租户之间、项目之间的 agents/state/logs 互不可见
5. **垂直场景是模板，不是平台边界** — 趋势分析、股票监控等作为预置模板加速上手

---

## 二、现状：已经有什么

| 能力 | 状态 | 位置 |
|------|------|------|
| 租户数据隔离（文件系统） | ✅ | `platform/local_tenant.py` |
| CLI 创建项目 | ✅ | `forge-agent new --tenant` |
| CLI 列出项目 | ✅ | `forge-agent list-projects` |
| Agent 类型库（scraper/analyzer/chief） | ✅ | `builtin/agent_types/` |
| Web：创建/编辑/删除 Agent | ✅ | `/agents/new`, API CRUD |
| Web：创建/编辑/删除 Pipeline | ✅ | `/pipelines/new`, API CRUD |
| Web：运行 Pipeline + 查看历史 | ✅ | `/pipelines/{id}/run`, `/runs` |
| 多租户 LLM 配置 | ✅ | `platform/llm_config.py` |
| YAML 配置校验 | ✅ | `platform/config_validator.py` |
| Docker 部署 | ✅ | `Dockerfile`, `docker-compose.yml` |

**一句话：单租户内的「自建 Agent + Pipeline」已经能跑，但平台层还不支持多用户自助入驻。**

---

## 三、缺口：离「部署后用户自助」还差什么

```text
现在：
  forge-agent up --tenant-id acme --project-id trend_watch
  → 启动时锁死一个租户+一个项目
  → 没有登录、没有切换租户/项目、没有自助注册

目标：
  forge-agent up
  → 任何授权用户登录
  → 看到自己租户下的所有项目
  → 新建项目 → 自建 Agent/Pipeline → 运行
```

| 缺口 | 影响 | 优先级 |
|------|------|--------|
| **G1** 启动时不锁死租户/项目，改为请求级路由 | 多租户共用一套服务 | P0 |
| **G2** Web 项目 CRUD（新建/列表/切换/删除） | 用户不用 CLI 建项目 | P0 |
| **G3** 租户选择与隔离（URL 或 Session 绑定 tenant） | 用户只看到自己的数据 | P0 |
| **G4** 基础认证（登录 + API Key 或简单账号） | 防止未授权访问 | P0 |
| **G5** 首次使用引导（Onboarding 空状态页） | 降低上手门槛 | P1 |
| **G6** 租户级 LLM 配置 UI | 用户自己配 API Key | P1 |
| **G7** 运行 Trace 展示 | 用户能复盘每次执行 | P1 |
| **G8** 真实工具接入（替换 placeholder） | Pipeline 跑真数据 | P2 |

---

## 四、实施阶段（按你的目标重排）

### Sprint A — 多租户 Web 路由（P0，约 3 天）

**目标**：一套 `forge-agent up` 服务多个租户/项目，不再启动时锁死。

| ID | 任务 | 验收标准 |
|----|------|----------|
| A1 | URL 路由改为 `/t/{tenant_id}/p/{project_id}/...` | 访问不同 URL 看到不同项目数据 |
| A2 | `create_app()` 改为无状态：从 request 解析 tenant/project | 不再在启动时绑定单一 project |
| A3 | 中间件：根据路径加载 `LocalTenant` + `project_root` | 所有现有页面/API 在新路由下正常工作 |
| A4 | 首页改为租户项目列表（或重定向到上次访问的项目） | 打开 `/` 能看到项目选择 |
| A5 | Web API：`POST /api/tenants/{tid}/projects` 创建项目 | 浏览器可新建项目，无需 CLI |

**出口**：

```bash
forge-agent up
# http://localhost:8787/t/acme/p/proj1/     → acme 的 proj1
# http://localhost:8787/t/bob/p/proj2/      → bob 的 proj2（数据隔离）
```

---

### Sprint B — 认证与租户归属（P0，约 4 天）

**目标**：部署到公网后，只有登录用户能操作自己的租户数据。

| ID | 任务 | 验收标准 |
|----|------|----------|
| B1 | 简单用户模型：user → tenant_id 映射（文件或 SQLite） | 用户只属于一个租户（v1 简化） |
| B2 | 登录页 + Session Cookie（或 JWT） | 未登录访问 `/t/...` 跳转登录 |
| B3 | 注册流程：注册即创建新租户（`tenant_id` = 用户名或 UUID） | 新用户注册后自动有自己的命名空间 |
| B4 | 鉴权中间件：用户只能访问自己 `tenant_id` 下的路径 | 跨租户访问返回 403 |
| B5 | 管理员 bootstrap：首个部署时创建 admin 租户 | `FORGE_ADMIN_TOKEN` 或首次启动向导 |

**出口**：

```bash
# 用户 A 注册 → 自动创建 tenant user_a
# 用户 B 注册 → 自动创建 tenant user_b
# A 无法访问 /t/user_b/...
```

---

### Sprint C — 自助创建体验打磨（P1，约 1 周）

**目标**：用户登录后，零 CLI 完成「建项目 → 建 Agent → 建 Pipeline → 运行」。

| ID | 任务 | 验收标准 |
|----|------|----------|
| C1 | 项目工作台：空状态引导（「创建第一个 Agent」） | 新项目有清晰引导 |
| C2 | Agent 创建表单：按类型动态渲染参数字段 | 选 scraper 出现 keyword/platform/tool |
| C3 | Pipeline 创建：可视化选 Agent + 指定 Chief | 不需要懂 YAML |
| C4 | 运行页：动态 payload 表单（根据 pipeline 需要填 keyword 等） | 一键运行 |
| C5 | 结果页：各 Agent 报告 + Chief 汇总结构化展示 | 非技术人员能读懂 |
| C6 | 可选：预置模板「从模板创建项目」（trend-analysis 等） | 加速冷启动 |

**出口**：新用户注册 → 5 分钟内完成第一个 Pipeline 运行。

---

### Sprint D — 平台运维能力（P1，约 3 天）

| ID | 任务 | 验收标准 |
|----|------|----------|
| D1 | 租户级 LLM 配置页面（provider + API Key） | Web 设置 DeepSeek Key，不需改文件 |
| D2 | Trace 集成到 launcher，Web 展示运行详情 | 每次 run 可看各 agent 耗时 |
| D3 | `docker-compose.yml` 加 volume 持久化 `~/.forge-agent` | 重启不丢数据 |
| D4 | 环境变量文档：`FORGE_SECRET_KEY`, `FORGE_DATA_DIR` 等 | 部署文档完整 |

---

### Sprint E — 质量与真实数据（P2，按需）

| ID | 任务 | 验收标准 |
|----|------|----------|
| E1 | 多租户 E2E 测试（注册 → 建项目 → 建 agent → 运行） | CI 通过 |
| E2 | 接入真实 scraper（从 `examples/toy_trend_demo` 迁移） | 工具非 placeholder |
| E3 | SaaS 扩展预留：`DBTenant` 接口与 `LocalTenant` 行为一致 | 未来可换存储后端 |

---

## 五、执行顺序

```text
Sprint A  多租户 Web 路由          ← 最先做，否则「部署一套多人用」不成立
    │
Sprint B  认证与租户归属
    │
Sprint C  自助创建体验打磨
    │
Sprint D  平台运维（LLM 配置、Trace、Docker）
    │
Sprint E  测试 + 真实工具（按需）
```

---

## 六、验收总入口

完成后，一个**从未用过 forge-agent 的用户**应能：

```text
1. 访问 https://your-forge-agent.example.com
2. 注册账号（自动获得独立租户）
3. 点击「新建项目」
4. 点击「+ Agent」→ 选 scraper → 填 keyword/platform → 保存
5. 再建 2 个 Agent，点击「+ Pipeline」→ 勾选它们 → 指定 Chief → 保存
6. 点击「运行」→ 填参数 → 看到各 Agent 报告和 Chief 汇总
7. 在「运行历史」里查看过往结果
8. 另一个用户注册后，完全看不到第一个用户的数据
```

管理员只需：

```bash
docker compose up -d
# 或
forge-agent up --host 0.0.0.0 --port 8787
```

---

## 七、进度跟踪

| Sprint | 状态 | 说明 |
|--------|------|------|
| A 多租户 Web 路由 | ⬜ | |
| B 认证与租户归属 | ⬜ | |
| C 自助创建体验 | ⬜ | 部分页面已有，需串联 |
| D 平台运维 | ⬜ | |
| E 质量与真实数据 | ⬜ | |

---

## 八、与旧计划的关系

| 文档 | 定位 |
|------|------|
| `docs/tasks/STATUS.md` | 引擎建设（98% 完成），归档参考 |
| `ROADMAP.md` | 战略全景，Phase 5 与本计划一致 |
| **`PLAN.md`** | **当前执行入口**，聚焦「部署 + 多租户自助」 |

### 2026-07-03 决策更新

- **产品核心**：可部署的多租户自服务平台，用户自建 Agent/Pipeline
- **趋势分析**：作为预置模板和内置工具，不是产品边界
- **Web 优先**：CLI/TUI 保留给开发者，终端用户只用浏览器
- **v1 简化**：一个用户 = 一个租户；组织内多用户共享租户放到 v2
