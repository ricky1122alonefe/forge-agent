# Your First Agent

A step-by-step guide to building a complete agent with forge-agent.

## Prerequisites

- [Installation](installation.md) completed
- Basic Python knowledge
- Understanding of async/await

## Step 1: Define the Agent

Every agent extends `BaseAgent` and implements three required methods:

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict

@register_agent(domain="weather", tags=["api", "weather"])
class WeatherAgent(BaseAgent):
    agent_id = "weather.current"
    name = "Weather Agent"
    domain = "weather"
    description = "Fetches current weather for a location"

    async def observe(self, ctx: AgentContext) -> dict:
        """Gather information from the environment."""
        location = ctx.config.get("location", "Beijing")
        return {"location": location}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        """Make a decision based on observations."""
        location = observation["location"]
        # In a real agent, you'd call a weather API here
        return {
            "action": "fetch_weather",
            "location": location,
        }

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        """Execute the decision and return a report."""
        location = decision["location"]
        # Simulated weather data
        weather_data = {
            "temperature": 22,
            "condition": "sunny",
            "humidity": 45,
        }

        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[f"Weather in {location}: {weather_data}"],
            confidence=0.95,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Step 2: Test the Agent

```python
import asyncio
from forge_agent import AgentContext

async def test_weather_agent():
    agent = WeatherAgent()
    ctx = AgentContext(
        scope_id="test-001",
        scope_name="weather-test",
        config={"location": "Shanghai"},
    )

    report = await agent.run(ctx)

    print(f"Agent: {report.name}")
    print(f"Verdict: {report.verdict}")
    print(f"Confidence: {report.confidence}")
    print(f"Evidence: {report.evidence}")

asyncio.run(test_weather_agent())
```

## Step 3: Add to a Pipeline

```python
from forge_agent import Pipeline, PipelineNode, NodeType, PipelineEngine

# Create pipeline
pipeline = Pipeline(pipeline_id="weather.v1")

# Add weather agent node
pipeline.add_node(PipelineNode(
    node_id="weather",
    node_type=NodeType.AGENT,
    agent_id="weather.current",
    next_nodes=["aggregate"],
))

# Add aggregator node
pipeline.add_node(PipelineNode(
    node_id="aggregate",
    node_type=NodeType.AGGREGATOR,
))

async def run_weather_pipeline():
    ctx = AgentContext(
        scope_id="pipeline-001",
        scope_name="weather-pipeline",
        config={"location": "Tokyo"},
    )

    engine = PipelineEngine()
    state = await engine.run(pipeline, ctx)

    board = state["board"]
    print(f"Pipeline completed: {board.verdict}")
    print(f"Reports: {len(board.reports)}")

asyncio.run(run_weather_pipeline())
```

## Step 4: Add Logging

```python
from forge_agent.observability import get_logger, bind_context

logger = get_logger(__name__)

@register_agent(domain="weather", tags=["api", "weather", "logged"])
class LoggedWeatherAgent(WeatherAgent):
    agent_id = "weather.logged"

    async def observe(self, ctx: AgentContext) -> dict:
        bind_context(agent_id=self.agent_id, run_id=ctx.run_id)
        logger.info("observing", location=ctx.config.get("location"))
        return await super().observe(ctx)

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        logger.info("deciding", observation=observation)
        return await super().decide(ctx, observation)

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        logger.info("acting", decision=decision)
        report = await super().act(ctx, decision)
        logger.info("completed", verdict=report.verdict)
        return report
```

## Step 5: Version Your Agent

```bash
# List versions
forge-agent list

# Activate a specific version
forge-agent activate weather.logged --version 1

# Rollback
forge-agent rollback weather.logged --version 0
```

## What's Next?

- [Concepts: BaseAgent](../concepts/base-agent.md) — understand the agent lifecycle
- [Guides: Create an Agent](../guides/create-agent.md) — advanced patterns
- [API Reference](../api/core.md) — complete API documentation
