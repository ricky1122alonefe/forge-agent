"""End-to-end test: football pipeline.

We re-import + re-register agents INSIDE the test so the autouse
registry-cleaning fixture doesn't wipe them out.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from forge_agent.pipeline.pipeline import NodeType, Pipeline, PipelineNode  # noqa: E402


def _build() -> Pipeline:
    p = Pipeline(pipeline_id="football.test")
    p.add_node(
        PipelineNode("intel", NodeType.AGENT, agent_id="football.intel", next_nodes=["chief"])
    )
    p.add_node(PipelineNode("chief", NodeType.AGENT, agent_id="generic.chief", next_nodes=["agg"]))
    p.add_node(PipelineNode("agg", NodeType.AGGREGATOR))
    return p


@pytest.mark.asyncio
async def test_football_pipeline_runs():
    from forge_agent.core.context import AgentContext
    from forge_agent.pipeline.engine import PipelineEngine
    from forge_agent.registry.registry import get_registry

    # Force a fresh re-import of the agent modules (the autouse fixture
    # may have cleared their registrations).
    for mod_name in [
        "forge_agent.builtin.chief_agent",
        "examples.football_match_agent.agents",
    ]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
        else:
            importlib.import_module(mod_name)

    registry = get_registry()
    assert "football.intel" in registry, f"Available: {registry.list()}"
    assert "generic.chief" in registry, f"Available: {registry.list()}"

    ctx = AgentContext(
        scope_id="x",
        scope_name="Qatar vs Indonesia",
        domain="football",
        payload={"odds_snapshot": {"home": 1.45, "draw": 4.2, "away": 6.5}},
    )
    state = await PipelineEngine().run(_build(), ctx)
    assert "intel" in state["reports"]
    r = state["reports"]["intel"]
    assert r.domain == "football"
    assert r.evidence
    assert state["board"] is not None
