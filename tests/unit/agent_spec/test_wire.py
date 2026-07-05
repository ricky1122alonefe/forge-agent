"""Tests for primitive wiring rules (A9.1)."""

from __future__ import annotations

from forge_agent.agent_spec.models import AgentPrimitive
from forge_agent.agent_spec.wire import suggest_team_mode, validate_wiring


class TestWireValidation:
    def test_synthesizer_requires_upstream(self) -> None:
        errors = validate_wiring([AgentPrimitive.SYNTHESIZER, AgentPrimitive.FETCHER])
        assert any("upstream" in e for e in errors)

    def test_fetcher_synth_chain_ok(self) -> None:
        errors = validate_wiring(
            [AgentPrimitive.FETCHER, AgentPrimitive.FETCHER, AgentPrimitive.SYNTHESIZER]
        )
        assert errors == []

    def test_monitor_not_valid_upstream(self) -> None:
        errors = validate_wiring([AgentPrimitive.MONITOR, AgentPrimitive.SYNTHESIZER])
        assert any("monitor" in e for e in errors)

    def test_suggest_sequential_with_synthesizer(self) -> None:
        assert (
            suggest_team_mode([AgentPrimitive.FETCHER, AgentPrimitive.SYNTHESIZER]) == "sequential"
        )

    def test_suggest_parallel_without_synthesizer(self) -> None:
        assert suggest_team_mode([AgentPrimitive.FETCHER, AgentPrimitive.SEARCHER]) == "parallel"
