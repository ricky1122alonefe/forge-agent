# forge-agent Roadmap

## 愿景

forge-agent 是一个**低代码 / 无代码的多租户 agent 平台**：

- 部署一套系统，每个租户拥有自己的 projects、agents、pipelines。
- 用户不写代码，通过项目启动后的交互界面配置 agent 和 pipeline。
- 架构同时支持**本地单点部署**与**企业服务（SaaS）**。

---

## 架构设计

```text
forge-agent/
├── platform/                  # 租户与项目隔离层
│   ├── tenant.py              # Tenant 抽象
│   ├── local_tenant.py        # 本地单点实现（默认）
│   └── db_tenant.py           # 企业服务实现（后续）
├── builtin/                   # 系统内置能力
│   ├── agent_types/           # agent 类型库
│   │   ├── scraper.yaml
│   │   ├── analyzer.yaml
│   │   └── chief.yaml
│   └── tools/                 # 内置工具（后续）
├── project/                   # 项目级运行时
│   ├── launcher.py            # 项目启动器
│   └── tui.py                 # 终端交互界面
├── cli/                       # 命令行入口
├── core/                      # 核心引擎（已有）
└── templates/                 # 项目模板
    └── config-driven/
```

租户数据本地默认存放：

```text
~/.forge-agent/
└── tenants/
    └── {tenant_id}/
        ├── projects/
        │   └── {project_id}/
        │       ├── agents/
        │       ├── pipelines/
        │       ├── tools/
        │       ├── configs/
        │       ├── state/
        │       └── run.py
        └── shared/
            └── agent_types/
```

---

## Phase 1：多租户与项目隔离

目标：支持 `forge-agent new <project> --tenant <tenant_id>`，项目数据按租户隔离。

- [x] 1.1 定义 `Tenant` 抽象接口（`platform/tenant.py`）
  - 方法：`create_project(project_id)`、`get_project_path(project_id)`、`list_projects()`、`get_state_path(project_id)`
  - 验收标准：能实例化 MockTenant，实现以上方法

- [x] 1.2 实现 `LocalTenant`（`platform/local_tenant.py`）
  - 根目录：`~/.forge-agent/tenants/{tenant_id}/`
  - 自动创建目录结构
  - 验收标准：`LocalTenant("acme").create_project("trend_demo")` 生成正确目录

- [x] 1.3 修改 `forge-agent new` 支持 `--tenant`
  - 默认租户：`default`
  - 项目路径改为租户隔离路径
  - 验收标准：
    ```bash
    forge-agent new trend_demo --tenant acme
    forge-agent new trend_demo --tenant bob
    ```
    两个同名项目互不干扰

- [x] 1.4 新增 `forge-agent list-projects --tenant <tenant_id>`
  - 列出某租户下的所有项目
  - 验收标准：`forge-agent list-projects --tenant acme` 输出项目列表

- [x] 1.5 单元测试
  - 测试 `LocalTenant` 创建、隔离、列表功能
  - 验收标准：`pytest tests/platform/` 通过

---

## Phase 2：内置 Agent 类型库

目标：定义可复用的 agent 类型模板，供项目启动后选择创建。

- [x] 2.1 定义 Agent 类型 schema（`builtin/agent_types/_schema.yaml`）
  - 字段：type_id、name、description、params、prompt_template、output_schema、tools
  - 验收标准：schema 可被解析并校验

- [x] 2.2 创建 `scraper` 类型（`builtin/agent_types/scraper.yaml`）
  - 参数：keyword、platform、tool
  - 默认 prompt：抓取某平台数据并判断趋势
  - 输出 schema：verdict、confidence、risk、evidence、recommended_action
  - 验收标准：用类型定义生成一个 agent YAML，结构正确

- [x] 2.3 创建 `analyzer` 类型（`builtin/agent_types/analyzer.yaml`）
  - 参数：input_from（上游 agent id）、focus
  - 默认 prompt：基于上游数据做深度分析
  - 验收标准：同上

- [x] 2.4 创建 `chief` 类型（`builtin/agent_types/chief.yaml`）
  - 参数：agent_inputs（上游 agents 列表）
  - 默认 prompt：汇总多个 agent 报告，输出最终决策
  - 验收标准：同上

- [x] 2.5 实现 `AgentTypeRegistry`
  - 从 `builtin/agent_types/` 加载所有类型
  - 从 `tenants/{tenant}/shared/agent_types/` 加载租户自定义类型
  - 验收标准：`registry.list()` 返回所有可用类型

- [x] 2.6 新增 `forge-agent agent-types` 命令
  - 列出系统 + 租户下的所有 agent 类型
  - 验收标准：命令行能输出类型列表

---

## Phase 3：项目启动后的交互式配置

目标：进入项目目录后运行 `python run.py`，通过 TUI 创建 agent/pipeline 并运行。

- [x] 3.1 创建 `project/launcher.py`
  - 启动项目时检测当前 tenant/project 上下文
  - 如果 agents/pipelines 为空，进入 TUI 引导
  - 验收标准：`python run.py` 在空项目下不报错，进入菜单

- [x] 3.2 创建 `project/tui.py` 终端交互菜单
  - 主菜单：
    1. Create agent
    2. Create pipeline
    3. Run pipeline
    4. Exit
  - 验收标准：TUI 能显示菜单并接收选择

- [x] 3.3 实现 "Create agent" 流程
  - 列出可用 agent 类型
  - 根据类型参数逐个提问（keyword、platform 等）
  - 生成 `agents/{agent_id}.yaml`
  - 验收标准：TUI 中完成创建后，文件存在且格式正确

- [x] 3.4 实现 "Create pipeline" 流程
  - 列出项目内已创建的 agents
  - 选择哪些 agents 并行运行
  - 是否指定 chief
  - 生成 `pipelines/{pipeline_id}.yaml`
  - 验收标准：生成 pipeline 配置能被执行

- [x] 3.5 修改 `run.py` 模板
  - 调用 `launcher.run()`
  - 保留 `--pipeline <id>` 参数，支持非交互式运行
  - 验收标准：项目生成后 `python run.py` 能启动 TUI

- [x] 3.6 集成测试
  - 在 TUI 中创建 agent → 创建 pipeline → 运行 pipeline
  - 验收标准：端到端跑通，结果保存到 `state/`

---

## Phase 4：运行与结果隔离

目标：pipeline 执行结果按租户/项目隔离存储，支持历史查询。

- [x] 4.1 运行结果按 `Tenant` / 项目隔离存储
  - 运行结果写入 `tenants/{tenant}/projects/{project}/state/`
  - 验收标准：运行后 state 目录存在结果文件

- [x] 4.2 定义结果文件格式
  - 文件名：`{timestamp}_{pipeline_id}.json`
  - 内容：run_id、timestamp、pipeline_id、payload、agent_reports、chief_summary、metadata
  - 同时写入 `latest.json`
  - 验收标准：结果文件可被解析

- [x] 4.3 新增 `run.py --list` 命令
  - 列出历史运行结果
  - 验收标准：`python run.py --list` 输出历史记录

- [x] 4.4 新增 `run.py --rerun <run_id>` 命令
  - 使用历史 payload 重新运行某次 pipeline
  - 验收标准：重跑成功

- [x] 4.5 测试多租户隔离
  - 在 tenant acme 和 tenant bob 下分别运行同名 pipeline
  - 验收标准：两者的结果文件不互相覆盖

---

## Phase 5：企业服务扩展（未来）

目标：把本地单点架构扩展为 SaaS 服务。

- [ ] 5.1 实现 `DBTenant`
  - 租户、项目、agents、pipelines、state 存入数据库
  - 验收标准：接口与 `LocalTenant` 行为一致

- [ ] 5.2 添加 REST API 层
  - 项目：创建、列表、获取、删除
  - Agent：创建、列表、获取
  - Pipeline：创建、运行、获取结果
  - 验收标准：通过 curl 能完成完整流程

- [ ] 5.3 用户认证与租户鉴权
  - API key / JWT 认证
  - 用户只能访问自己租户的数据
  - 验收标准：跨租户访问返回 403

- [ ] 5.4 Web UI（可选）
  - 替换 TUI，提供浏览器界面
  - 验收标准：在浏览器里完成 create → run 全流程

---

## 当前冲刺（先做 Phase 1 + Phase 2）

1. 完成租户抽象与本地实现（Phase 1）
2. 完成内置 agent 类型库（Phase 2）
3. 验证：`forge-agent new trend_demo --tenant acme` 能生成隔离项目，且能看到内置 agent 类型

---

## Phase 6：横向基础设施

目标：补齐平台级通用能力，支撑 Phase 1-5 稳定运行。

- [x] 6.1 内置工具注册中心
  - 文件：`platform/tool_registry.py`
  - 接口：`register(tool)`、`list(tenant_id=None)`、`get(name)`
  - 内置工具：微博热搜、小红书搜索、得物搜索、抖音热点（placeholder 实现）
  - 验收：`forge-agent tools --tenant acme` 列出可用工具

- [x] 6.2 LLM 配置与多租户隔离
  - 文件：`platform/llm_config.py`
  - 层级：系统默认 → 租户覆盖 → 项目覆盖
  - 支持 provider：deepseek、openai、qwen 等
  - 验收：tenant acme 用 deepseek，tenant bob 用 openai，互不影响

- [x] 6.3 YAML 配置校验
  - 文件：`platform/config_validator.py`
  - 校验 agent/pipeline YAML 的 schema、必填字段、工具引用是否存在
  - 验收：引用不存在 tool 时，`python run.py` 启动即报错并给出明确提示

- [x] 6.4 错误处理与友好提示
  - 统一异常类型：`ForgeAgentError`、`ConfigError`、`ToolError`、`LLMError`
  - CLI/TUI 遇到错误时输出中文提示
  - 验收：LLM key 缺失时提示"请设置 DEEPSEEK_API_KEY"而不是抛 traceback

- [ ] 6.5 日志与 Trace
  - agent 执行日志按 `tenants/{tenant}/projects/{project}/logs/` 隔离
  - 支持结构化 JSON 日志
  - 一次运行生成一个 trace_id，串联所有 agent 输入/输出/耗时
  - 验收：`python run.py --pipeline trend` 后 logs 目录有对应 trace

---

## Phase 7：生态与插件

目标：把能力封装成可复用、可分享的包。

- [ ] 7.1 Skill 包规范
  - 一个 skill = 工具 + agent 类型 + pipeline 模板 + skill.yaml 元信息
  - 目录：`skills/{skill_name}/`
  - 验收：能定义并加载一个 skill

- [ ] 7.2 内置 Skill：社媒抓取
  - skill 名：`social-scraper-skill`
  - 包含：weibo、xiaohongshu、dewu、douyin 工具
  - 验收：安装后新租户自动获得这些工具

- [ ] 7.3 Agent 模板市场
  - 预置完整 pipeline 模板：trend-analysis、stock-monitor、football-monitor
  - 命令：`forge-agent new my_project --template trend-analysis`
  - 验收：用模板创建的项目自带完整 agents 和 pipelines

- [ ] 7.4 Skill / 模板安装命令
  - `forge-agent skill install <name>`
  - `forge-agent skill list`
  - `forge-agent skill uninstall <name>`
  - 验收：能安装、列出、卸载 skill

---

## Phase 8：SaaS 商业化

目标：让企业客户可以共用一套 forge-agent 服务。

- [ ] 8.1 多租户资源配额
  - 限制维度：agent 数量、pipeline 数量、LLM token、存储空间
  - 文件：`platform/quota.py`
  - 验收：超配额时返回明确错误，不静默失败

- [ ] 8.2 角色与权限模型
  - 角色：owner、admin、editor、viewer
  - 权限粒度：租户级 + 项目级
  - 验收：viewer 不能修改 pipeline，跨项目访问返回 403

- [ ] 8.3 API Key 与认证
  - 支持 API key 和 JWT
  - 每个租户可生成多个 API key
  - 验收：无 key / 错误 key 访问返回 401

- [ ] 8.4 调用计费与统计
  - 统计：pipeline 运行次数、token 消耗、API 调用次数
  - 导出：按租户/项目/时间维度生成账单
  - 验收：能导出某租户上月的消耗报表

---

## Phase 9：测试与质量

目标：保证平台稳定、可维护。

- [ ] 9.1 单元测试覆盖
  - tenant、tool registry、agent type registry、config validator 都要有单元测试
  - 覆盖率目标：> 80%
  - 验收：`pytest` 通过且 coverage 达标

- [ ] 9.2 集成测试
  - 场景：`forge-agent new` → 创建 agent → 创建 pipeline → 运行 → 检查 state
  - 使用临时目录隔离，不污染真实 `~/.forge-agent`
  - 验收：集成测试脚本稳定通过

- [ ] 9.3 E2E 测试
  - 工具链：CLI → TUI → pipeline 运行 → 结果查看
  - 验收：完整流程通过一次

- [ ] 9.4 代码质量门禁
  - pre-commit 强制 ruff、ruff-format、yaml 校验
  - 已配置，后续保持每次提交前通过
  - 验收：`pre-commit run --all-files` 通过

- [ ] 9.5 CI/CD
  - GitHub Actions / 等价 CI
  - 每次 PR 跑 lint、test、E2E
  - 验收：CI 流水线绿色

---

## Phase 10：部署与运维

目标：让 forge-agent 能方便地部署和监控。

- [ ] 10.1 Docker 镜像
  - 提供 Dockerfile
  - 支持通过环境变量注入配置
  - 验收：`docker build -t forge-agent .` 成功

- [ ] 10.2 docker-compose 单点部署
  - 文件：`docker-compose.yml`
  - 一键启动：单容器 + 本地卷挂载
  - 验收：`docker compose up` 后 CLI 可用

- [ ] 10.3 Kubernetes / Helm（企业）
  - Helm chart 支持多实例、配置外部数据库
  - 验收：能在 k8s 集群部署

- [ ] 10.4 监控与告警
  - 暴露 metrics 端点
  - 关键指标：pipeline 运行次数、错误率、LLM token 消耗
  - 验收：接入 Prometheus / Grafana 可见基础 dashboard

- [ ] 10.5 日志收集
  - 支持输出到 stdout / 文件 / 外部日志服务
  - 验收：企业部署时日志可集中收集

---

## 当前冲刺（按顺序执行）

1. **Phase 1**：租户抽象与项目隔离
2. **Phase 2**：内置 agent 类型库
3. **Phase 6.1 + 6.2**：工具注册中心 + LLM 配置（支撑 demo 跑真实数据）
4. **Phase 3**：项目启动后的 TUI 交互配置
5. **Phase 4**：运行与结果隔离

后续再按顺序推进 Phase 5（企业服务）、Phase 7（生态）、Phase 8（商业化）、Phase 9（测试）、Phase 10（部署）。

---

## 验收总入口

完成上述阶段后，应能在命令行完成：

```bash
# 1. 创建多租户项目
forge-agent new trend_demo --tenant acme

# 2. 进入项目，交互式创建 agent 和 pipeline
cd ~/.forge-agent/tenants/acme/projects/trend_demo
python run.py

# 3. 运行 pipeline
python run.py --pipeline trend

# 4. 查看结果
python run.py --list
```
