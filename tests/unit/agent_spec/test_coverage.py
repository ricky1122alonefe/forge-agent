"""Tests for scenario coverage report (A4.3)."""

from __future__ import annotations

from forge_agent.agent_spec.coverage import compute_scenario_coverage


class TestCoverage:
    def test_matrix_coverage_meets_target(self) -> None:
        report = compute_scenario_coverage()
        assert report["total"] == 20
        assert report["routing_pass"] >= 18
        assert report["target_met"] is True
        assert report["routing_rate"] >= 0.9
        assert "fetcher" in report["by_primitive"]

    def test_scenario_entries_include_routing_flags(self) -> None:
        report = compute_scenario_coverage()
        assert len(report["scenarios"]) == 20
        assert all("routing_ok" in row for row in report["scenarios"])
