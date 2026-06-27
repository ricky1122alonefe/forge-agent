# forge-agent

> **A universal, contract-driven Agent factory & orchestration engine.**
> Base never changes. Capabilities are pluggable. Business is generated on demand.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/forge-agent.svg)](https://pypi.org/project/forge-agent/)
[![CI status](https://github.com/ricky1122alonefe/forge-agent/actions/workflows/test.yml/badge.svg)](https://github.com/ricky1122alonefe/forge-agent/actions)
[![codecov](https://codecov.io/gh/ricky1122alonefe/forge-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/ricky1122alonefe/forge-agent)
[![Downloads](https://static.pepy.tech/badge/forge-agent)](https://pepy.tech/project/forge-agent)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Why forge-agent?

Vertical Agent tools (sports, stock, social) lock you into one domain. `forge-agent`
is the **base** that lets you **generate** any vertical Agent on demand:

| | Vertical tools | forge-agent |
|---|---|---|
| **Extension model** | config tweaks | **code-level dynamic generation** |
| **Orchestration** | fixed pipeline | **flexible DAG** (parallel / conditional) |
| **Self-iteration** | prompt tuning only | **code + prompt dual iteration** |
| **MCP / external** | preset bindings | **unified capability bus** |
| **Reusability** | business-coupled | **business-decoupled** |

## ✨ Features

- 🏗️ **Strong contract** — `BaseAgent` with 3 must-implement + 5 optional capabilities
- ⚡ **Unified LLM layer** — OpenAI, Anthropic, Gemini, Ollama, Mock (all in 4-line API)
- 🎨 **Code generation** — natural language → validated, sandboxed, injected Agent
- 🔌 **MCP native** — first-class Model Context Protocol support
- 📊 **DAG pipelines** — sequential, parallel, conditional, aggregator
- 📝 **Structured logging** — structlog + contextvars (auto agent_id / run_id injection)
- 🗄️ **Versioned CodeStore** — every generation archived, rollback-able, diff-able
- 🛡️ **Sandbox by default** — generated code runs in isolated subprocess
- 🔍 **59 tests passing** — and growing

## 📦 Installation

```bash
pip install forge-agent
```

Or with all extras:

```bash
pip install "forge-agent[llm,mcp,search]"
```

## 🚀 Quick Start

```python
import asyncio
from forge_agent import (
    BaseAgent, AgentContext, AgentReport,
    register_agent, Pipeline, PipelineNode, NodeType,
    PipelineEngine, Verdict,
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

## 🏛️ Architecture (4 layers)

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

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](https://github.com/ricky1122alonefe/forge-agent/blob/main/CONTRIBUTING.md)
for the full guide, and check out the [good first issues](https://github.com/ricky1122alonefe/forge-agent/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## 📜 License

[MIT](LICENSE) © 2026 ricky1122alonefe
