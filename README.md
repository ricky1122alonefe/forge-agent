# forge-agent

> **A universal, contract-driven Agent factory & orchestration engine.**
> Base never changes. Capabilities are pluggable. Business is generated on demand.

[![PyPI version](https://img.shields.io/pypi/v/forge-agent.svg)](https://pypi.org/project/forge-agent/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI status](https://github.com/ricky1122alonefe/forge-agent/actions/workflows/test.yml/badge.svg)](https://github.com/ricky1122alonefe/forge-agent/actions)
[![codecov](https://codecov.io/gh/ricky1122alonefe/forge-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/ricky1122alonefe/forge-agent)
[![Downloads](https://static.pepy.tech/badge/forge-agent)](https://pepy.tech/project/forge-agent)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![GitHub stars](https://img.shields.io/github/stars/ricky1122alonefe/forge-agent?style=social)](https://github.com/ricky1122alonefe/forge-agent/stargazers)

[📚 Documentation](https://forge-agent.readthedocs.io/) · [🐛 Report a bug](https://github.com/ricky1122alonefe/forge-agent/issues) · [💡 Request a feature](https://github.com/ricky1122alonefe/forge-agent/issues) · [💬 Discussions](https://github.com/ricky1122alonefe/forge-agent/discussions)

---

## Why forge-agent?

Vertical Agent tools (sports, stock, social) lock you into one domain. `forge-agent`
is the **base** that lets you **generate** any vertical Agent on demand:

| | Vertical tools (e.g. Defy) | forge-agent |
|---|---|---|
| **Extension model** | config tweaks | **code-level dynamic generation** |
| **Orchestration** | fixed pipeline | **flexible DAG** (parallel / conditional) |
| **Self-iteration** | prompt tuning only | **code + prompt dual iteration** |
| **MCP / external** | preset bindings | **unified capability bus** |
| **Reusability** | business-coupled | **business-decoupled** |

## Installation

### 前置要求

- **Python 3.10+**（脚本会自动检测并安装）
- **macOS / Linux / Windows**

### 一键安装

**macOS / Linux:**

```bash
git clone https://github.com/ricky1122alonefe/forge-agent.git
cd forge-agent
bash scripts/install.sh
```

**Windows:**

```cmd
git clone https://github.com/ricky1122alonefe/forge-agent.git
cd forge-agent
scripts\install.bat
```

安装脚本会自动：
1. 检测系统是否安装了 Python 3.10+，没有则自动安装（macOS/Linux）
2. 创建虚拟环境 `.venv/`
3. 安装 forge-agent 及所有依赖
4. 创建全局命令链接，让你在任何目录都能使用 `forge-agent` 命令

### 验证安装

```bash
forge-agent doctor
```

### 手动安装

如果你更喜欢手动控制：

```bash
git clone https://github.com/ricky1122alonefe/forge-agent.git
cd forge-agent

# 创建虚拟环境（需要 Python 3.10+）
python3.12 -m venv .venv        # macOS/Linux
python -m venv .venv            # Windows

# 激活虚拟环境
source .venv/bin/activate       # macOS/Linux
.venv\Scripts\activate          # Windows

# 安装
pip install -e ".[all]"
```

### 可选依赖组

| 组 | 安装命令 | 包含 |
|---|---|---|
| `all` | `pip install "forge-agent[all]"` | 全部 |
| `llm` | `pip install "forge-agent[llm]"` | openai, anthropic |
| `mcp` | `pip install "forge-agent[mcp]"` | MCP SDK |
| `search` | `pip install "forge-agent[search]"` | httpx, tavily |
| `otel` | `pip install "forge-agent[otel]"` | OpenTelemetry |
| `dashboard` | `pip install "forge-agent[dashboard]"` | FastAPI, uvicorn, Jinja2 |
| `dev` | `pip install -e ".[dev]"` | pytest, ruff, mypy, mkdocs |

## Quick Start

### 1. 创建项目

```bash
forge-agent new my-project --template basic
cd my-project
pip install -e .
```

可选模板：`basic`、`stock`、`football`、`social`、`office`

### 2. 配置 LLM

```bash
forge-agent llm list          # 查看可用 provider
forge-agent llm test deepseek # 测试连通性
```

### 3. 生成 Agent

```bash
forge-agent generate "帮我写一个爬取豆瓣电影Top250的爬虫"
```

### 4. 管理 Agent

```bash
forge-agent list                    # 查看所有 Agent
forge-agent history <agent_id>      # 版本历史
forge-agent use <agent_id> --latest # 切换版本
forge-agent rollback <agent_id>     # 回滚
```

### 5. 启动 Dashboard

```bash
forge-agent dashboard  # http://localhost:8765
```

### Python API 示例

```python
import asyncio
from forge_agent import (
    BaseAgent, AgentContext, AgentReport,
    register_agent, get_registry, Pipeline, PipelineNode, NodeType,
    PipelineEngine, AgentBoard, Verdict,
)


@register_agent(domain="hello", tags=["example"])
class HelloAgent(BaseAgent):
    agent_id = "hello.basic"
    name = "Hello Agent"
    domain = "hello"

    async def observe(self, ctx):
        return {"greeting": f"hello, {ctx.scope_name}"}

    async def decide(self, ctx, observation):
        return {"say": observation["greeting"]}

    async def act(self, ctx, decision):
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.NEUTRAL,
            evidence=[decision["say"]],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )


async def main():
    pipeline = Pipeline(pipeline_id="hello.v1")
    pipeline.add_node(PipelineNode(
        node_id="hi", node_type=NodeType.AGENT,
        agent_id="hello.basic", next_nodes=["done"],
    ))
    pipeline.add_node(PipelineNode(
        node_id="done", node_type=NodeType.AGGREGATOR,
    ))
    state = await PipelineEngine().run(
        pipeline,
        AgentContext(scope_id="1", scope_name="world"),
    )
    print(state["board"].to_dict())


asyncio.run(main())
```

## Architecture (4 layers)

```
┌─────────────────────────────────────────────────────────────┐
│  Generator Layer   LLM-driven Agent code generation + validate│
├─────────────────────────────────────────────────────────────┤
│  Pipeline Layer    DAG / parallel / conditional / aggregator  │
├─────────────────────────────────────────────────────────────┤
│  Registry + Scheduler    agent lifecycle & task execution    │
├─────────────────────────────────────────────────────────────┤
│  Core Layer        BaseAgent + 5 mandatory capabilities       │
│                    (log / search / learn / iterate / prompt) │
└─────────────────────────────────────────────────────────────┘
```

## The 5 mandatory capabilities (on `BaseAgent`)

1. **Log**            — `self.log(...)` via pluggable `LoggerProtocol`
2. **Search**         — `await self.search(...)` via `SearcherProtocol`
3. **Self-learning**  — `reflect()` + `learn()` (default: in-memory)
4. **Self-iteration** — `evolve()` (v0.4+)
5. **Custom prompt**  — `self.prompt_manager.render(...)` (versioned, file-backed)

## Project layout

```
forge-agent/
├── src/forge_agent/         # main package (src layout)
│   ├── core/                # base abstractions
│   ├── registry/            # registration & lifecycle
│   ├── scheduler/           # task execution
│   ├── pipeline/            # DAG orchestration
│   ├── prompt/              # versioned prompt management
│   ├── learning/            # reflection / memory / optimizer
│   ├── search/              # web / knowledge search
│   ├── observability/       # log / events / metrics
│   ├── mcp/                 # MCP gateway & permissions
│   ├── generator/           # code generator (v0.2+)
│   ├── builtin/             # reference agents
│   └── utils/
├── examples/
│   └── football_match_agent/   # migrated from guess_you_like
├── tests/                   # unit + integration + e2e
├── docs/                    # mkdocs documentation
└── pyproject.toml
```

## Unified logging (structlog)

Every `BaseAgent` run is automatically tagged with `agent_id`, `run_id`,
and `domain` via `contextvars` — no manual plumbing required. Any log
line emitted from inside `observe()` / `decide()` / `act()` /
`reflect()` / `learn()` (or any nested helper) carries those fields.

```python
from forge_agent.observability import configure_logging, get_logger

# Call once at startup (CLI does this automatically).
configure_logging()                       # console + INFO (dev)
# or
configure_logging(json=True, log_file="logs/forge-agent.log")

log = get_logger("forge_agent.demo")
log.info("doing stuff", count=3)          # auto-includes bound context
```

### Renderers

| Mode      | When                                | Output                          |
|-----------|-------------------------------------|---------------------------------|
| `console` | interactive TTY (default in dev)    | colored, human-readable         |
| `json`    | CI / server / pipe / `FORGE_LOG_JSON=1` | one JSON object per line       |

### Env vars (read at `configure_logging()` time)

| Variable                | Effect                                                |
|-------------------------|-------------------------------------------------------|
| `FORGE_LOG_LEVEL`       | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |
| `FORGE_LOG_JSON`        | `1` to force JSON output                              |
| `FORGE_LOG_FILE`        | `1` to also tee to a rotating file                    |
| `FORGE_LOG_FILE_PATH`   | path for the rotating file (default `logs/forge-agent.log`) |

### Inspecting logs

```bash
# Tail the last 50 lines (human-readable)
forge-agent logs

# Follow in real time
forge-agent logs --follow

# Raw JSON (pipe to jq)
forge-agent logs --json --tail 200 | jq 'select(.level == "error")'
```

### Adding your own context

```python
from forge_agent.observability import bind_context, unbind_context

bind_context(request_id="req-123", user="alice")
log.info("handling request")
# → "handling request" with request_id and user automatically attached
unbind_context("request_id", "user")
```

Concurrent asyncio tasks get isolated contexts automatically — two
parallel agents running with different `agent_id`s will never see each
other's bindings.

## Roadmap

- [x] **v0.1** — Base abstractions + Registry + Scheduler + Pipeline
- [x] **v0.2** — LLM-driven code generator + sandbox + inject
- [x] **v0.3** — MCP native integration + observability dashboard + Docker
- [ ] **v0.4** — Self-iteration loop + hot reload + production governance

## Migration from `guess_you_like/match_agents/`

See `examples/football_match_agent/` for a 1:1 mapping from the v1
function-based agents to v2 `BaseAgent` subclasses.

## License

MIT
