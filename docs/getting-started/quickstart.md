# Quickstart

Get up and running with forge-agent in 5 minutes.

## 1. Create Your First Agent

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict

@register_agent(domain="demo", tags=["quickstart"])
class DemoAgent(BaseAgent):
    agent_id = "demo.basic"
    name = "Demo Agent"
    domain = "demo"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"input": ctx.config.get("input", "hello")}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"action": "respond", "message": observation["input"]}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[decision["message"]],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## 2. Run the Agent

```python
import asyncio
from forge_agent import AgentContext

async def main():
    agent = DemoAgent()
    ctx = AgentContext(scope_id="test-1", scope_name="quickstart")
    report = await agent.run(ctx)
    print(report.to_dict())

asyncio.run(main())
```

## 3. Build a Pipeline

```python
from forge_agent import Pipeline, PipelineNode, NodeType, PipelineEngine

pipeline = Pipeline(pipeline_id="demo.v1")

pipeline.add_node(PipelineNode(
    node_id="demo",
    node_type=NodeType.AGENT,
    agent_id="demo.basic",
    next_nodes=["done"],
))

pipeline.add_node(PipelineNode(
    node_id="done",
    node_type=NodeType.AGGREGATOR,
))

async def run_pipeline():
    ctx = AgentContext(scope_id="pipeline-1", scope_name="demo")
    state = await PipelineEngine().run(pipeline, ctx)
    print(state["board"].to_dict())

asyncio.run(run_pipeline())
```

## 4. Generate an Agent from Natural Language

```bash
forge-agent generate "monitor stock prices and alert on significant changes"
```

This creates a new agent in `generated_agents/` with:

- Validated Python code
- Type hints
- Docstrings
- MANIFEST.json metadata

## 5. List Your Agents

```bash
forge-agent list
```

## Next Steps

- [Create an Agent](../guides/create-agent.md) — detailed guide
- [Use LLM Providers](../guides/llm-providers.md) — configure OpenAI, Anthropic, etc.
- [Version & Deploy](../guides/version-deploy.md) — manage agent versions
- [API Reference](../api/core.md) — complete API documentation
