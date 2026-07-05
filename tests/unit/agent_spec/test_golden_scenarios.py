"""Golden scenario tests for AgentSpec generator (AGENT_PLAN A1.6)."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.models import AgentPrimitive
from forge_agent.agent_spec.smoke import smoke_run_spec
from forge_agent.agent_spec.writer import validate_spec


class TestGoldenScenarios:
    """Phase 1 three golden cases."""

    @pytest.mark.asyncio
    async def test_fetcher_weibo_trend(self) -> None:
        spec = generate_spec_rule_based(
            "分析 labubu 在微博的热度趋势",
            agent_id="golden_weibo",
            keyword="labubu",
        )
        assert spec.primitive == AgentPrimitive.FETCHER
        assert spec.template == "scraper_agent"
        assert not validate_spec(spec)
        smoke = await smoke_run_spec(spec)
        assert smoke["success"] is True

    @pytest.mark.asyncio
    async def test_searcher_industry_news(self) -> None:
        spec = generate_spec_rule_based(
            "搜索 AI 行业动态并给出趋势判断",
            agent_id="golden_search",
            keyword="AI",
        )
        assert spec.primitive == AgentPrimitive.SEARCHER
        assert spec.template == "search_agent"
        smoke = await smoke_run_spec(spec)
        assert smoke["success"] is True

    @pytest.mark.asyncio
    async def test_synthesizer_upstream_reports(self) -> None:
        spec = generate_spec_rule_based(
            "汇总上游多份 Agent 报告并给出综合结论",
            agent_id="golden_synth",
        )
        assert spec.primitive == AgentPrimitive.SYNTHESIZER
        assert spec.config["variables"]["reports"] == "reports"
        smoke = await smoke_run_spec(spec)
        assert smoke["success"] is True
