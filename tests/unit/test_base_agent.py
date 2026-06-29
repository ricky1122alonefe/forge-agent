"""Unit tests for BaseAgent contract."""

from __future__ import annotations

import pytest

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Verdict


def _make_demo():
    class _Demo(BaseAgent):
        agent_id = "test.demo"
        name = "Demo"
        domain = "test"

        async def observe(self, ctx):
            return {"x": 1}

        async def decide(self, ctx, obs):
            return {"y": obs["x"] + 1}

        async def act(self, ctx, dec):
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                verdict=Verdict.NEUTRAL,
                evidence=[f"y={dec['y']}"],
                run_id=ctx.run_id,
            )

    _Demo.__name__ = "_Demo"
    return _Demo


def _make_boom():
    class _Boom(BaseAgent):
        agent_id = "test.boom"
        name = "Boom"

        async def observe(self, ctx):
            raise RuntimeError("intentional")

        async def decide(self, ctx, obs):
            return {}

        async def act(self, ctx, dec):
            return AgentReport(agent_id=self.agent_id, name=self.name)

    _Boom.__name__ = "_Boom"
    return _Boom


@pytest.mark.asyncio
async def test_run_cycle():
    demo = _make_demo()
    agent = demo()
    ctx = AgentContext(scope_id="t1", scope_name="t")
    report = await agent.run(ctx)
    assert report.evidence == ["y=2"]
    assert report.run_id == ctx.run_id


@pytest.mark.asyncio
async def test_lifecycle():
    demo = _make_demo()
    agent = demo()
    assert agent.status.value == "uninitialized"
    await agent.initialize()
    assert agent.status.value == "ready"
    await agent.shutdown()
    assert agent.status.value == "shutdown"


@pytest.mark.asyncio
async def test_error_path_does_not_crash():
    boom = _make_boom()
    a = boom()
    ctx = AgentContext(scope_id="t", scope_name="t")
    r = await a.run(ctx)
    assert r.verdict.value == "risk"
    assert any("intentional" in w for w in r.warnings)
