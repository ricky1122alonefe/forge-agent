"""Tests for agent maturity ladder (A3.2)."""

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

    def test_connected_when_real_tools(self) -> None:
        m = compute_maturity(
            {
                "config": {"mock_mode": False, "tools": ["weibo.hot_search"]},
                "_meta": {"smoke_verified": True},
            }
        )
        assert m["stage"] == "connected"
