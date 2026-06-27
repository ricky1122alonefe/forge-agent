# Write a Custom Capability

Extend BaseAgent with custom capabilities.

## Overview

BaseAgent provides 5 built-in capabilities:

1. **log** — Structured logging
2. **search** — Web search
3. **learn** — Self-iteration
4. **iterate** — Code evolution
5. **prompt** — Prompt management

You can add custom capabilities to your agents.

## Custom Capability Pattern

```python
from forge_agent.core.capabilities import Capability

class CustomCapability(Capability):
    """A custom capability for agents."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.config = config or {}

    async def execute(self, ctx: dict) -> dict:
        """Execute the capability."""
        # Your implementation
        return {"result": "processed"}
```

## Example: Database Capability

```python
import sqlite3
from forge_agent.core.capabilities import Capability

class DatabaseCapability(Capability):
    """Database access capability."""

    def __init__(self, db_path: str):
        super().__init__({"db_path": db_path})
        self.db_path = db_path

    async def execute(self, ctx: dict) -> dict:
        query = ctx.get("query")
        params = ctx.get("params", [])

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return {"results": results}
```

## Using Custom Capabilities

```python
from forge_agent import BaseAgent, register_agent

@register_agent(domain="data", tags=["database"])
class DataAgent(BaseAgent):
    agent_id = "data.query"
    name = "Data Agent"
    domain = "data"

    def __init__(self):
        super().__init__()
        self.db = DatabaseCapability("/path/to/db.sqlite")

    async def observe(self, ctx: AgentContext) -> dict:
        result = await self.db.execute({
            "query": "SELECT * FROM users WHERE active = ?",
            "params": [1],
        })
        return {"users": result["results"]}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"user_count": len(observation["users"])}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[f"Found {decision['user_count']} users"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Example: Cache Capability

```python
from functools import lru_cache
from forge_agent.core.capabilities import Capability

class CacheCapability(Capability):
    """In-memory caching capability."""

    def __init__(self, max_size: int = 100):
        super().__init__({"max_size": max_size})
        self.cache = {}
        self.max_size = max_size

    async def execute(self, ctx: dict) -> dict:
        key = ctx.get("key")
        value = ctx.get("value")

        if value is not None:
            # Set
            if len(self.cache) >= self.max_size:
                # Evict oldest
                oldest = next(iter(self.cache))
                del self.cache[oldest]
            self.cache[key] = value
            return {"cached": True}
        else:
            # Get
            return {"value": self.cache.get(key)}
```

## Example: Notification Capability

```python
import httpx
from forge_agent.core.capabilities import Capability

class NotificationCapability(Capability):
    """Send notifications via webhook."""

    def __init__(self, webhook_url: str):
        super().__init__({"webhook_url": webhook_url})
        self.webhook_url = webhook_url

    async def execute(self, ctx: dict) -> dict:
        message = ctx.get("message")
        channel = ctx.get("channel", "default")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json={
                    "channel": channel,
                    "message": message,
                },
            )

        return {"sent": response.status_code == 200}
```

## Composing Capabilities

```python
@register_agent(domain="smart", tags=["multi-capability"])
class SmartAgent(BaseAgent):
    agent_id = "smart.agent"
    name = "Smart Agent"
    domain = "smart"

    def __init__(self):
        super().__init__()
        self.db = DatabaseCapability("/path/to/db.sqlite")
        self.cache = CacheCapability(max_size=100)
        self.notify = NotificationCapability("https://hooks.slack.com/...")

    async def observe(self, ctx: AgentContext) -> dict:
        # Check cache first
        cached = await self.cache.execute({"key": "users"})
        if cached["value"]:
            return {"users": cached["value"], "source": "cache"}

        # Query database
        result = await self.db.execute({
            "query": "SELECT * FROM users",
        })

        # Cache result
        await self.cache.execute({
            "key": "users",
            "value": result["results"],
        })

        return {"users": result["results"], "source": "database"}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"user_count": len(observation["users"])}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        # Send notification
        await self.notify.execute({
            "message": f"Processed {decision['user_count']} users",
            "channel": "alerts",
        })

        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[f"Processed {decision['user_count']} users"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Best Practices

1. **Single responsibility** — Each capability does one thing well
2. **Stateless when possible** — Avoid mutable state
3. **Handle errors** — Catch and log exceptions
4. **Document thoroughly** — Explain inputs and outputs
5. **Test independently** — Unit test each capability
