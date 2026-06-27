# Logging

forge-agent uses structlog for structured, context-aware logging.

## Overview

```python
from forge_agent.observability import get_logger, bind_context

logger = get_logger(__name__)

# Bind context
bind_context(agent_id="stock.monitor", run_id="run-123")

# Log with automatic context injection
logger.info("processing", symbol="AAPL", price=150.0)
```

Output (JSON):

```json
{
  "timestamp": "2026-06-27T10:00:00Z",
  "level": "info",
  "event": "processing",
  "agent_id": "stock.monitor",
  "run_id": "run-123",
  "symbol": "AAPL",
  "price": 150.0
}
```

## Configuration

```python
from forge_agent.observability import configure_logging

configure_logging(
    level="INFO",
    json_output=True,
    include_timestamp=True,
)
```

## Context Binding

### Bind Context

```python
from forge_agent.observability import bind_context, unbind_context, clear_context

# Add context
bind_context(agent_id="my-agent", scope="production")

# Remove specific keys
unbind_context("scope")

# Clear all context
clear_context()
```

### Automatic Context

Agents automatically bind context:

```python
class MyAgent(BaseAgent):
    async def observe(self, ctx: AgentContext) -> dict:
        # Context is automatically bound
        logger.info("observing")  # Includes agent_id, run_id
        return {}
```

## Structured Logging

### Log Levels

```python
logger.debug("debug message", detail="value")
logger.info("info message", count=42)
logger.warning("warning message", threshold=0.8)
logger.error("error message", error="timeout")
logger.critical("critical message", system="down")
```

### Exceptions

```python
try:
    risky_operation()
except Exception as e:
    logger.exception("operation failed", error=str(e))
```

## Log Processors

Customize log processing:

```python
from forge_agent.observability import configure_logging

configure_logging(
    processors=[
        "add_timestamp",
        "add_log_level",
        "format_json",
    ]
)
```

## Tracing Integration

Logs automatically include trace context:

```python
from forge_agent.observability import get_trace_manager

mgr = get_trace_manager()
trace = mgr.start_trace(pipeline_id="analysis")

logger.info("starting pipeline")
# Includes trace_id in log output
```

## CLI Commands

```bash
# View logs
forge-agent logs --agent stock.monitor --limit 100

# Follow logs
forge-agent logs --follow

# Filter by level
forge-agent logs --level ERROR
```

## Best Practices

1. **Use structured data** — Pass key-value pairs, not formatted strings
2. **Bind context early** — Bind agent_id and run_id at the start
3. **Log at boundaries** — Log at method entry/exit
4. **Include metrics** — Log durations, counts, sizes
5. **Use appropriate levels** — DEBUG for details, INFO for flow, ERROR for failures

## Example: Complete Logging

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict
from forge_agent.observability import get_logger, bind_context

logger = get_logger(__name__)

@register_agent(domain="analytics", tags=["logged"])
class AnalyticsAgent(BaseAgent):
    agent_id = "analytics.processor"
    name = "Analytics Agent"
    domain = "analytics"

    async def observe(self, ctx: AgentContext) -> dict:
        bind_context(agent_id=self.agent_id, run_id=ctx.run_id)
        logger.info("observe_start", scope=ctx.scope_name)

        data = await self.fetch_data()
        logger.info("observe_complete", records=len(data))

        return {"data": data}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        logger.info("decide_start")

        data = observation["data"]
        analysis = self.analyze(data)

        logger.info("decide_complete",
                    insights=len(analysis["insights"]),
                    confidence=analysis["confidence"])

        return analysis

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        logger.info("act_start", action=decision.get("action"))

        report = AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=decision["insights"],
            confidence=decision["confidence"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )

        logger.info("act_complete", verdict=report.verdict)
        return report
```
