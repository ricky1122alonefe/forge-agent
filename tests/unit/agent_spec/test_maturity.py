"""Tests for agent maturity ladder (A3.2 / A7)."""

from __future__ import annotations

from forge_agent.agent_spec.maturity import compute_maturity


class TestMaturity:
    def test_draft_when_mock_and_not_verified(self) -> None:
        m = compute_maturity({"config": {"mock_mode": True}, "mock_cases": [{"name": "x"}]})
        assert m["stage"] == "draft"

    def test_verified_after_smoke(self) -> None:
        m = compute_maturity(
            {
                "config": {"mock_mode": True},
                "_meta": {"smoke_verified": True},
                "mock_cases": [{"name": "x"}],
            }
        )
        assert m["stage"] == "verified"

    def test_mock_off_without_real_run_stays_verified(self) -> None:
        m = compute_maturity(
            {
                "config": {"mock_mode": False, "tools": ["weibo.hot_search"]},
                "_meta": {"smoke_verified": True},
            }
        )
        assert m["stage"] == "verified"
        assert "试跑" in m["next_step"]

    def test_connected_after_real_run_with_tools(self) -> None:
        m = compute_maturity(
            {
                "config": {"mock_mode": False, "tools": ["weibo.hot_search"]},
                "_meta": {"smoke_verified": True, "real_run_verified": True},
            }
        )
        assert m["stage"] == "connected"

    def test_production_after_real_run_without_tools(self) -> None:
        m = compute_maturity(
            {
                "config": {"mock_mode": False},
                "_meta": {"real_run_verified": True},
            }
        )
        assert m["stage"] == "production"
