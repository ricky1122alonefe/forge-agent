# BaseAgent

The `BaseAgent` is the foundation of every agent in forge-agent. It defines a standard lifecycle and contract that all agents must follow.

## Agent Lifecycle

Every agent execution follows this sequence:

```
observe → decide → act → reflect → learn
```

### Required Methods

All agents **must** implement these three methods:

#### `observe(ctx: AgentContext) -> dict`

Gather information from the environment.

```python
async def observe(self, ctx: AgentContext) -> dict:
    return {"data": await self.fetch_data()}
```

#### `decide(ctx: AgentContext, observation: dict) -> dict`

Make a decision based on observations.

```python
async def decide(self, ctx: AgentContext, observation: dict) -> dict:
    if observation["data"]["value"] > threshold:
        return {"action": "alert"}
    return {"action": "ignore"}
```

#### `act(ctx: AgentContext, decision: dict) -> AgentReport`

Execute the decision and return a structured report.

```python
async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
    return AgentReport(
        agent_id=self.agent_id,
        name=self.name,
        verdict=Verdict.POSITIVE,
        evidence=[decision["action"]],
        run_id=ctx.run_id,
        timestamp=ctx.timestamp,
    )
```

### Optional Methods

These methods have default no-op implementations:

#### `reflect(ctx: AgentContext, report: AgentReport) -> dict`

Analyze the outcome and extract lessons.

```python
async def reflect(self, ctx: AgentContext, report: AgentReport) -> dict:
    return {"lesson": "threshold was appropriate"}
```

#### `learn(ctx: AgentContext, reflection: dict) -> None`

Update internal state based on reflections.

```python
async def learn(self, ctx: AgentContext, reflection: dict) -> None:
    self.adjust_threshold(reflection["lesson"])
```

## AgentContext

The context object passed to every method:

```python
@dataclass
class AgentContext:
    scope_id: str          # Unique identifier for this execution scope
    scope_name: str        # Human-readable name
    run_id: str            # Unique run identifier
    timestamp: str         # ISO 8601 timestamp
    config: dict           # Runtime configuration
    metadata: dict         # Additional metadata
```

## AgentReport

The structured output from `act()`:

```python
@dataclass
class AgentReport:
    agent_id: str
    name: str
    verdict: Verdict       # POSITIVE, NEGATIVE, NEUTRAL
    evidence: list[str]
    confidence: float      # 0.0 to 1.0
    risk: float            # 0.0 to 1.0
    run_id: str
    timestamp: str
```

## Registration

Use the `@register_agent` decorator to register your agent:

```python
from forge_agent import register_agent

@register_agent(domain="finance", tags=["stock", "analysis"])
class StockAgent(BaseAgent):
    agent_id = "stock.analyzer"
    # ...
```

## Capabilities

BaseAgent provides 5 pluggable capabilities:

1. **log** — Structured logging (structlog)
2. **search** — Web search (Tavily, HTTPX)
3. **learn** — Self-iteration and optimization
4. **iterate** — Code evolution
5. **prompt** — Prompt management

Each capability can be customized or replaced.

## Example: Complete Agent

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict
from forge_agent.observability import get_logger

logger = get_logger(__name__)

@register_agent(domain="monitor", tags=["health", "api"])
class HealthMonitorAgent(BaseAgent):
    agent_id = "monitor.health"
    name = "Health Monitor"
    domain = "monitor"
    description = "Monitors API health endpoints"

    async def observe(self, ctx: AgentContext) -> dict:
        endpoints = ctx.config.get("endpoints", [])
        results = {}
        for endpoint in endpoints:
            status = await self.check_health(endpoint)
            results[endpoint] = status
        return {"health": results}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        unhealthy = [
            ep for ep, status in observation["health"].items()
            if status != "healthy"
        ]
        if unhealthy:
            return {"action": "alert", "endpoints": unhealthy}
        return {"action": "ok"}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        if decision["action"] == "alert":
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                verdict=Verdict.NEGATIVE,
                evidence=[f"Unhealthy: {decision['endpoints']}"],
                confidence=1.0,
                risk=0.8,
                run_id=ctx.run_id,
                timestamp=ctx.timestamp,
            )
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=["All endpoints healthy"],
            confidence=1.0,
            risk=0.0,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )

    async def reflect(self, ctx: AgentContext, report: AgentReport) -> dict:
        logger.info("reflecting", verdict=report.verdict)
        return {"status": "monitored"}

    async def learn(self, ctx: AgentContext, reflection: dict) -> None:
        logger.info("learning", reflection=reflection)
```
