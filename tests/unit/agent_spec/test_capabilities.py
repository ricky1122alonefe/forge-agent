"""Tests for optional agent capabilities (A9.4)."""

from __future__ import annotations

from forge_agent.agent_spec.capabilities import (
    detect_capabilities,
    merge_type_capabilities,
)
from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.models import AgentSpec


class TestCapabilities:
    def test_detect_memory_and_constraints(self) -> None:
        caps = detect_capabilities("记住历史并做合规审核")
        assert "memory" in caps
        assert "constraints" in caps

    def test_no_capabilities_by_default(self) -> None:
        assert detect_capabilities("分析 labubu 微博趋势") == []

    def test_apply_to_spec(self) -> None:
        spec = generate_spec_rule_based("记住上次分析并审核敏感词", agent_id="cap_test")
        assert "memory" in spec.capabilities
        assert "constraints" in spec.capabilities
        assert "memory" in spec.config
        assert spec.config["constraints"]["builtin"] == "compliance"

    def test_merge_type_capabilities(self) -> None:
        spec = AgentSpec(agent_id="typed", name="Typed", config={})
        merge_type_capabilities(spec, {"memory": True})
        assert "memory" in spec.config
