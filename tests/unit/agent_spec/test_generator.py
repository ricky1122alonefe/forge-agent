"""Unit tests for AgentSpec generator."""

from __future__ import annotations

from forge_agent.agent_spec.generator import (
    detect_primitive,
    extract_keyword,
    generate_spec_rule_based,
)
from forge_agent.agent_spec.models import AgentPrimitive
from forge_agent.agent_spec.writer import apply_spec, validate_spec


class TestAgentSpecGenerator:
    def test_extract_keyword_latin(self) -> None:
        assert extract_keyword("分析 labubu 微博趋势") == "labubu"

    def test_detect_fetcher(self) -> None:
        assert detect_primitive("抓取微博热搜") == AgentPrimitive.FETCHER

    def test_detect_searcher(self) -> None:
        assert detect_primitive("搜索行业报告") == AgentPrimitive.SEARCHER

    def test_detect_synthesizer(self) -> None:
        assert detect_primitive("汇总上游报告") == AgentPrimitive.SYNTHESIZER

    def test_apply_spec_writes_file(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="search_test")
        result = apply_spec(tmp_path, spec)
        assert result["success"] is True
        assert (tmp_path / "agents" / "search_test.yaml").exists()

    def test_validate_rejects_invalid_id(self) -> None:
        spec = generate_spec_rule_based("分析趋势", agent_id="bad id!")
        errors = validate_spec(spec)
        assert errors
