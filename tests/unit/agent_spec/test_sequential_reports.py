"""Sequential team runner injects upstream reports."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.writer import apply_spec
from forge_agent.core.factory import AgentFactory
from forge_agent.core.mission import Mission
from forge_agent.core.runner import TeamRunner
from forge_agent.core.team import Team
from forge_agent.storage import ForgeStore


@pytest.mark.asyncio
async def test_sequential_injects_reports_for_synthesizer(tmp_path) -> None:
    fetcher = generate_spec_rule_based("分析 demo 微博趋势", agent_id="seq_fetch", keyword="demo")
    synth = generate_spec_rule_based("汇总上游报告", agent_id="seq_synth")
    apply_spec(tmp_path, fetcher, overwrite=True)
    apply_spec(tmp_path, synth, overwrite=True)

    factory = AgentFactory()
    for yaml_file in (tmp_path / "agents").glob("*.yaml"):
        factory.load_yaml(yaml_file)

    team = Team(
        team_id="seq_team",
        name="Sequential",
        domain="generic",
        agent_ids=["seq_fetch", "seq_synth"],
        mode="sequential",
    )
    mission = Mission(
        mission_id="m1",
        name="seq test",
        team=team,
        payload={"keyword": "demo"},
    )
    board = await TeamRunner(store=ForgeStore(db_path=str(tmp_path / "test.db"))).run(mission)
    assert len(board.agents) == 2
    assert board.agents[-1].agent_id == "seq_synth"
