"""Tests for Agent CI gate (A10.1)."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.ci import CIGateError, run_ci_gate
from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.models import MockCase
from forge_agent.agent_spec.writer import apply_spec


class TestCIGate:
    def test_run_ci_gate_passes_valid_spec(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="ci_ok")
        results = run_ci_gate(spec)
        assert results
        assert all(r["success"] for r in results)

    def test_run_ci_gate_blocks_bad_expect_keys(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="ci_bad")
        spec.mock_cases = [
            MockCase(name="bad", input={"query": "x"}, expect_keys=["nonexistent_key"])
        ]
        with pytest.raises(CIGateError, match="CI gate blocked"):
            run_ci_gate(spec)

    def test_apply_spec_ci_gate_blocks_write(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="ci_block")
        spec.mock_cases = [
            MockCase(name="bad", input={"query": "x"}, expect_keys=["missing_field"])
        ]
        with pytest.raises(CIGateError):
            apply_spec(tmp_path, spec, ci_gate=True, auto_repair=False, judge_gate=False)
        assert not (tmp_path / "agents" / "ci_block.yaml").exists()

    def test_apply_spec_ci_gate_writes_on_pass(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="ci_write")
        result = apply_spec(tmp_path, spec, ci_gate=True)
        assert result["ci_gate"] is True
        assert (tmp_path / "agents" / "ci_write.yaml").exists()
