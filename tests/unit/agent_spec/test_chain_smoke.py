"""Tests for compose full-chain mock smoke (A10.2)."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.chain_smoke import smoke_compose_chain
from forge_agent.agent_spec.compose import compose_from_requirement


class TestChainSmoke:
    @pytest.mark.asyncio
    async def test_dual_platform_chain(self) -> None:
        plan = compose_from_requirement(
            "抓微博和小红书 labubu 热度，再汇总成一份报告",
            keyword="labubu",
        )
        result = await smoke_compose_chain(plan)
        assert result["success"] is True
        assert result["agents_run"] == 3
        assert result["mode"] == "sequential"
        assert result["last_agent_id"] == plan.specs[-1].agent_id

    @pytest.mark.asyncio
    async def test_single_agent_skips_chain(self) -> None:
        plan = compose_from_requirement("搜索 AI 行业动态", keyword="AI")
        result = await smoke_compose_chain(plan)
        assert result.get("skipped") is True
