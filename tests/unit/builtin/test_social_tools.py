"""Tests for built-in social tools (P3.4)."""

from __future__ import annotations

import pytest

from forge_agent.builtin.tools.executor import execute_tool
from forge_agent.builtin.tools.mode import ToolMode
from forge_agent.builtin.tools.social import weibo_hot_search


class TestSocialTools:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_fixture(self) -> None:
        result = await weibo_hot_search("labubu", tool_mode="mock")
        assert result["source"] == "mock"
        assert result["platform"] == "weibo"
        assert len(result["items"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_tool_via_registry(self) -> None:
        result = await execute_tool("weibo.hot_search", keyword="labubu", tool_mode=ToolMode.MOCK)
        assert result["source"] == "mock"
        assert result["keyword"] == "labubu"

    @pytest.mark.asyncio
    async def test_auto_mode_degrades_without_network(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fail_probe(_url: str, *, timeout: float = 8.0) -> bool:
            return False

        monkeypatch.setattr(
            "forge_agent.builtin.tools.social._http_probe",
            _fail_probe,
        )
        result = await execute_tool("weibo.hot_search", keyword="labubu", tool_mode=ToolMode.AUTO)
        assert result["source"] == "fallback"
        assert result["items"]

    @pytest.mark.asyncio
    async def test_real_mode_raises_when_probe_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fail_probe(_url: str, *, timeout: float = 8.0) -> bool:
            return False

        monkeypatch.setattr(
            "forge_agent.builtin.tools.social._http_probe",
            _fail_probe,
        )
        with pytest.raises(RuntimeError, match="Live probe failed"):
            await execute_tool("weibo.hot_search", keyword="labubu", tool_mode=ToolMode.REAL)
