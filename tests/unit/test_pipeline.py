"""Unit tests for Pipeline + PipelineEngine + Aggregator.

Agents are defined inside each test for proper isolation.
"""

from __future__ import annotations

import pytest

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Verdict
from forge_agent.pipeline.aggregator import Aggregator
from forge_agent.pipeline.engine import PipelineEngine
from forge_agent.pipeline.pipeline import NodeType, Pipeline, PipelineNode
from forge_agent.registry.decorators import register_agent


def _up_cls():
    class _Up(BaseAgent):
        agent_id = "p.up"
        name = "Up"

        async def observe(self, ctx):
            return {"v": 1}

        async def decide(self, ctx, o):
            return {"v": o["v"] * 2}

        async def act(self, ctx, d):
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                verdict=Verdict.LEAN_POSITIVE,
                confidence=0.8,
                risk=0.1,
                weight=1.0,
                evidence=[f"v={d['v']}"],
            )

    _Up.__name__ = "_Up"
    return _Up


def _down_cls():
    class _Down(BaseAgent):
        agent_id = "p.down"
        name = "Down"

        async def observe(self, ctx):
            return {"v": 5}

        async def decide(self, ctx, o):
            return {"v": o["v"]}

        async def act(self, ctx, d):
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                verdict=Verdict.LEAN_NEGATIVE,
                confidence=0.6,
                risk=0.5,
                weight=1.0,
                evidence=[f"v={d['v']}"],
            )

    _Down.__name__ = "_Down"
    return _Down


def _side_cls():
    class _Side(BaseAgent):
        agent_id = "p.side"
        name = "Side"

        async def observe(self, ctx):
            return {"v": 10}

        async def decide(self, ctx, o):
            return {"v": o["v"]}

        async def act(self, ctx, d):
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                verdict=Verdict.LEAN_POSITIVE,
                confidence=0.7,
                risk=0.2,
                weight=1.0,
                evidence=[f"v={d['v']}"],
            )

    _Side.__name__ = "_Side"
    return _Side


def _build() -> Pipeline:
    p = Pipeline(pipeline_id="p.test")
    p.add_node(PipelineNode("up", NodeType.AGENT, agent_id="p.up", next_nodes=["down"]))
    p.add_node(PipelineNode("down", NodeType.AGENT, agent_id="p.down", next_nodes=["agg"]))
    p.add_node(PipelineNode("agg", NodeType.AGGREGATOR))
    return p


def _build_parallel() -> Pipeline:
    p = Pipeline(pipeline_id="p.parallel")
    p.add_node(PipelineNode("root", NodeType.AGENT, agent_id="p.up", next_nodes=["left", "right"]))
    p.add_node(PipelineNode("left", NodeType.AGENT, agent_id="p.down", next_nodes=["agg"]))
    p.add_node(PipelineNode("right", NodeType.AGENT, agent_id="p.side", next_nodes=["agg"]))
    p.add_node(PipelineNode("agg", NodeType.AGGREGATOR))
    return p


@pytest.mark.asyncio
async def test_pipeline_runs_two_agents_and_aggregates():
    register_agent()(_up_cls())
    register_agent()(_down_cls())
    p = _build()
    state = await PipelineEngine().run(p, AgentContext(scope_id="1", scope_name="x"))
    assert "up" in state["reports"]
    assert "down" in state["reports"]
    board = state["board"]
    assert board is not None
    assert board.ok is True
    assert board.summary["n_agents"] == 2
    assert board.summary["avg_risk"] == pytest.approx(0.3, abs=1e-6)


@pytest.mark.asyncio
async def test_hard_risk_guard_triggers():
    register_agent()(_up_cls())
    register_agent()(_down_cls())
    p = _build()
    ctx = AgentContext(scope_id="1", scope_name="x")
    state = await PipelineEngine(aggregator=Aggregator(hard_risk_threshold=0.4)).run(p, ctx)
    board = state["board"]
    assert board.ok is False
    assert any("hard risk" in g for g in board.hard_guards)


@pytest.mark.asyncio
async def test_parallel_mode_executes_sibling_nodes():
    register_agent()(_up_cls())
    register_agent()(_down_cls())
    register_agent()(_side_cls())
    p = _build_parallel()
    ctx = AgentContext(scope_id="1", scope_name="x")
    state = await PipelineEngine(execution_mode="parallel").run(p, ctx)
    assert "root" in state["reports"]
    assert "left" in state["reports"]
    assert "right" in state["reports"]
    board = state["board"]
    assert board is not None
    assert board.summary["n_agents"] == 3
