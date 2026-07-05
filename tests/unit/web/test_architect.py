"""Tests for natural-language pipeline architect (P4.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge_agent.platform.local_tenant import LocalTenant
from forge_agent.web.architect import apply_plan, extract_keyword, generate_plan_rule_based


class TestArchitect:
    def test_extract_keyword_from_quotes(self) -> None:
        assert extract_keyword("分析「labubu」在微博的热度") == "labubu"

    def test_rule_plan_weibo_xhs(self) -> None:
        plan = generate_plan_rule_based("分析 labubu 在微博和小红书的热度趋势")
        assert plan["keyword"] == "labubu"
        assert len(plan["agents"]) == 2
        ids = {a["agent_id"] for a in plan["agents"]}
        assert "weibo_analyst" in ids
        assert "xhs_analyst" in ids

    def test_apply_plan_writes_files(self, tmp_path: Path) -> None:
        tenant = LocalTenant("acme", root_dir=tmp_path / "data")
        project_root = tenant.create_project("demo")
        plan = generate_plan_rule_based("分析 popmart 在微博的趋势", keyword="popmart")
        result = apply_plan(project_root, plan)
        assert result["pipeline_id"] == "nl_popmart"
        assert (project_root / "agents" / "weibo_analyst.yaml").exists()
        assert (project_root / "pipelines" / "nl_popmart.yaml").exists()
        pipeline = yaml.safe_load((project_root / "pipelines" / "nl_popmart.yaml").read_text())
        assert "weibo_analyst" in pipeline["team"]["agent_ids"]

    @pytest.mark.asyncio
    async def test_generate_plan_async(self) -> None:
        from forge_agent.web.architect import generate_plan

        plan = await generate_plan("分析 labubu 在得物的趋势", use_llm=False)
        assert plan["planner"] == "rule"
        assert any(a["agent_id"] == "dewu_analyst" for a in plan["agents"])
