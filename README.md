# forge-agent

> **A universal, contract-driven Agent factory & orchestration engine.**
> Base never changes. Capabilities are pluggable. Business is generated on demand.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status: v0.1.0-alpha](https://img.shields.io/badge/status-v0.1.0--alpha-orange)]()

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

```bash
git clone https://github.com/ricky1122alonefe/forge-agent.git
cd forge-agent
pip install -e ".[dev]"
```

## Quick start

```python
import asyncio
from forge_agent import (
    BaseAgent, AgentContext, AgentReport,
    register_agent, get_registry, Pipeline, PipelineNode, NodeType,
    PipelineEngine, AgentBoard, Verdict, Action,
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

- [x] **v0.1** — Base abstractions + Registry + Scheduler + Pipeline (this release)
- [ ] **v0.2** — LLM-driven code generator + sandbox + inject
- [ ] **v0.3** — MCP native integration + visualization + observability dashboard
- [ ] **v0.4** — Self-iteration loop + hot reload + production governance

## Migration from `guess_you_like/match_agents/`

See `examples/football_match_agent/` for a 1:1 mapping from the v1
function-based agents to v2 `BaseAgent` subclasses.

## License

MIT
