"""Tests for single-agent run (AGENT_PLAN A6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.writer import apply_spec
from forge_agent.platform.local_tenant import LocalTenant
from forge_agent.project.agent_runner import default_run_payload, run_single_agent


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    tenant = LocalTenant("acme", root_dir=tmp_path / "data")
    root = tenant.create_project("demo")
    spec = generate_spec_rule_based(
        "搜索 AI 行业动态",
        agent_id="search_demo",
        keyword="AI",
    )
    apply_spec(root, spec, overwrite=True)
    return root


class TestAgentRunner:
    def test_default_payload_from_mock_cases(self, project_root: Path) -> None:
        from forge_agent.web.data import get_agent

        agent = get_agent(project_root, "search_demo")
        assert agent is not None
        payload = default_run_payload(agent)
        assert "query" in payload or "keyword" in payload

    @pytest.mark.asyncio
    async def test_run_single_agent_mock(self, project_root: Path) -> None:
        result = await run_single_agent(project_root, "acme", "search_demo", {})
        assert result["success"] is True
        assert result["mock_mode"] is True
        assert result["verdict"]
        assert result["report"]["agent_id"] == "search_demo"
        assert "run_id" in result

    def test_mark_real_run_verified_updates_maturity(self, project_root: Path) -> None:
        from forge_agent.agent_spec.generator import generate_spec_rule_based
        from forge_agent.agent_spec.maturity import compute_maturity
        from forge_agent.agent_spec.writer import apply_spec, mark_real_run_verified
        from forge_agent.web.data import get_agent

        spec = generate_spec_rule_based(
            "对用户评论做情感分类",
            agent_id="reasoner_prod",
            keyword="评论",
        )
        spec.config["mock_mode"] = False
        apply_spec(project_root, spec, overwrite=True)
        mark_real_run_verified(project_root, "reasoner_prod")

        agent = get_agent(project_root, "reasoner_prod")
        assert agent is not None
        assert agent["_meta"]["real_run_verified"] is True
        assert compute_maturity(agent)["stage"] == "production"
