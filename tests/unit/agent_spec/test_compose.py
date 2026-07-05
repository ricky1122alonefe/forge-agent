"""Tests for multi-agent compose (A9.2)."""

from __future__ import annotations

import yaml

from forge_agent.agent_spec.compose import apply_compose_plan, compose_from_requirement
from forge_agent.agent_spec.models import AgentPrimitive
from forge_agent.agent_spec.smoke import smoke_run_spec_sync


class TestCompose:
    def test_dual_platform_decomposition(self) -> None:
        plan = compose_from_requirement(
            "抓微博和小红书 labubu 热度，再汇总成一份报告",
            keyword="labubu",
        )
        assert plan.wiring_errors == []
        assert len(plan.specs) == 3
        assert plan.specs[-1].primitive == AgentPrimitive.SYNTHESIZER
        assert plan.mode == "sequential"
        assert len(plan.agent_ids) == 3

    def test_apply_writes_agents_and_pipeline(self, tmp_path) -> None:
        plan = compose_from_requirement(
            "抓微博和小红书 popmart 热度并汇总",
            keyword="popmart",
            pipeline_id="popmart_team",
        )
        result = apply_compose_plan(tmp_path, plan)
        assert result["pipeline_id"] == "popmart_team"
        for agent_id in plan.agent_ids:
            assert (tmp_path / "agents" / f"{agent_id}.yaml").exists()
        pipeline = yaml.safe_load(
            (tmp_path / "pipelines" / "popmart_team.yaml").read_text(encoding="utf-8")
        )
        assert pipeline["team"]["mode"] == "sequential"
        assert pipeline["team"]["agent_ids"] == plan.agent_ids

    def test_compose_smoke_all_specs(self) -> None:
        plan = compose_from_requirement(
            "抓微博和抖音 labubu 数据并汇总",
            keyword="labubu",
        )
        for spec in plan.specs:
            smoke = smoke_run_spec_sync(spec)
            assert smoke["success"] is True, smoke
