"""Tests for self-healing CI and Judge gate (A13)."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.ci import CIGateError, run_ci_gate
from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.models import MockCase
from forge_agent.agent_spec.repair import repair_spec_from_ci_failure, run_ci_with_repair
from forge_agent.agent_spec.writer import apply_spec


class TestSelfHealing:
    def test_repair_trims_bad_expect_keys(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="repair_trim")
        spec.mock_cases = [
            MockCase(name="bad", input={"query": "x"}, expect_keys=["nonexistent_key"])
        ]
        results = [
            {
                "success": False,
                "case": "bad",
                "missing_keys": ["nonexistent_key"],
                "decision_keys": ["verdict", "confidence"],
            }
        ]
        repaired, fixes = repair_spec_from_ci_failure(spec, results)
        assert fixes
        assert "nonexistent_key" not in repaired.mock_cases[0].expect_keys

    def test_run_ci_with_repair_fixes_bad_spec(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="repair_ok")
        spec.mock_cases = [MockCase(name="bad", input={"query": "x"}, expect_keys=["missing_key"])]
        repaired, results, meta = run_ci_with_repair(spec, judge_gate=True)
        assert meta["repaired"] is True
        assert all(r["success"] for r in results)
        assert repaired.mock_cases[0].expect_keys

    def test_apply_spec_auto_repair_writes(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="repair_apply")
        spec.mock_cases = [MockCase(name="bad", input={"query": "x"}, expect_keys=["bogus_key"])]
        result = apply_spec(tmp_path, spec, ci_gate=True, auto_repair=True, judge_gate=True)
        assert result["repair_meta"]["repaired"] is True
        assert (tmp_path / "agents" / "repair_apply.yaml").exists()


class TestJudgeGate:
    def test_judge_gate_passes_good_mock(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="judge_ok")
        results = run_ci_gate(spec, judge_gate=True)
        assert results[0].get("judge", {}).get("score", 0) >= 0.55

    def test_judge_gate_blocks_low_quality_mock(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="judge_bad")
        spec.config["mock_response"] = (
            '{"verdict": "lean_neutral", "confidence": 0.05, "risk": 0.9, '
            '"evidence": [], "recommended_action": "hold", "metrics": {}}'
        )
        with pytest.raises(CIGateError, match="Judge CI blocked"):
            run_ci_gate(spec, judge_gate=True, judge_min_score=0.55)

    def test_repair_fixes_judge_failure(self) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="judge_repair")
        spec.config["mock_response"] = (
            '{"verdict": "lean_neutral", "confidence": 0.05, "risk": 0.9, '
            '"evidence": [], "recommended_action": "hold", "metrics": {}}'
        )
        _, results, meta = run_ci_with_repair(spec, judge_gate=True)
        assert meta["repaired"] is True
        assert results[0]["judge"]["score"] >= 0.55

    def test_apply_without_auto_repair_still_blocks(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="no_repair")
        spec.mock_cases = [
            MockCase(name="bad", input={"query": "x"}, expect_keys=["missing_field"])
        ]
        with pytest.raises(CIGateError):
            apply_spec(tmp_path, spec, ci_gate=True, auto_repair=False, judge_gate=False)
