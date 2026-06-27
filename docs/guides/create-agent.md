# Create an Agent

A comprehensive guide to creating agents with forge-agent.

## Basic Agent

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict

@register_agent(domain="example", tags=["basic"])
class BasicAgent(BaseAgent):
    agent_id = "example.basic"
    name = "Basic Agent"
    domain = "example"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"input": ctx.config.get("input")}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"action": "process"}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=["processed"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Agent with State

```python
@register_agent(domain="counter", tags=["stateful"])
class CounterAgent(BaseAgent):
    agent_id = "counter.basic"
    name = "Counter Agent"
    domain = "counter"

    def __init__(self):
        super().__init__()
        self.count = 0

    async def observe(self, ctx: AgentContext) -> dict:
        self.count += 1
        return {"count": self.count}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"count": observation["count"]}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[f"Count: {decision['count']}"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Agent with External APIs

```python
import httpx

@register_agent(domain="api", tags=["http"])
class APIClientAgent(BaseAgent):
    agent_id = "api.client"
    name = "API Client Agent"
    domain = "api"

    async def observe(self, ctx: AgentContext) -> dict:
        url = ctx.config.get("url")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return {"data": response.json()}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        data = observation["data"]
        return {"processed": len(data)}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[f"Processed {decision['processed']} items"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Agent with Error Handling

```python
from forge_agent.observability import get_logger

logger = get_logger(__name__)

@register_agent(domain="robust", tags=["error-handling"])
class RobustAgent(BaseAgent):
    agent_id = "robust.agent"
    name = "Robust Agent"
    domain = "robust"

    async def observe(self, ctx: AgentContext) -> dict:
        try:
            data = await self.fetch_data()
            return {"data": data, "error": None}
        except Exception as e:
            logger.error("observe_failed", error=str(e))
            return {"data": None, "error": str(e)}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        if observation["error"]:
            return {"action": "fallback", "error": observation["error"]}
        return {"action": "process", "data": observation["data"]}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        if decision["action"] == "fallback":
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                verdict=Verdict.NEGATIVE,
                evidence=[f"Error: {decision['error']}"],
                confidence=0.0,
                run_id=ctx.run_id,
                timestamp=ctx.timestamp,
            )

        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=["Success"],
            confidence=1.0,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Agent with Reflection

```python
@register_agent(domain="learning", tags=["reflective"])
class LearningAgent(BaseAgent):
    agent_id = "learning.agent"
    name = "Learning Agent"
    domain = "learning"

    def __init__(self):
        super().__init__()
        self.lessons = []

    async def observe(self, ctx: AgentContext) -> dict:
        return {"input": ctx.config.get("input")}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"action": "process"}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=["processed"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )

    async def reflect(self, ctx: AgentContext, report: AgentReport) -> dict:
        lesson = f"Run {ctx.run_id}: {report.verdict}"
        return {"lesson": lesson}

    async def learn(self, ctx: AgentContext, reflection: dict) -> None:
        self.lessons.append(reflection["lesson"])
        logger.info("learned", lesson=reflection["lesson"], total=len(self.lessons))
```

## Testing Your Agent

```python
import asyncio
from forge_agent import AgentContext

async def test_agent():
    agent = BasicAgent()
    ctx = AgentContext(
        scope_id="test-1",
        scope_name="test",
        config={"input": "hello"},
    )

    report = await agent.run(ctx)

    assert report.verdict == Verdict.POSITIVE
    assert report.confidence >= 0.0
    print("Test passed!")

asyncio.run(test_agent())
```

## Best Practices

1. **Keep agents focused** — One agent, one responsibility
2. **Use structured logging** — Bind context early
3. **Handle errors gracefully** — Return NEGATIVE verdict on failure
4. **Set confidence appropriately** — High confidence for certain outcomes
5. **Test thoroughly** — Unit test each lifecycle method
