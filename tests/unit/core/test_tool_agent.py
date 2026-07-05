"""Tests for ToolAgent template (P3.4)."""

from __future__ import annotations

from typing import Any

import pytest

from forge_agent.core.context import AgentContext
from forge_agent.core.templates.tool_agent import ToolAgent


class TestToolAgent:
    @pytest.mark.asyncio
    async def test_mock_mode_skips_tools(self) -> None:
        agent = ToolAgent(
            {
                "mock_mode": True,
                "platform": "weibo",
                "tools": ["weibo.hot_search"],
                "mock_response": '{"verdict":"lean_positive","confidence":0.8,"risk":0.1,'
                '"evidence":["mock"],"recommended_action":"watch","metrics":{}}',
                "output_mapping": {
                    "verdict": "verdict",
                    "confidence": "confidence",
                    "risk": "risk",
                    "evidence": "evidence",
                    "recommended_action": "recommended_action",
                },
            }
        )
        ctx = AgentContext(
            scope_id="run", scope_name="Run", domain="generic", payload={"keyword": "labubu"}
        )
        report = await agent.run(ctx)
        assert report.raw["data"]["skipped_tools"] is True

    @pytest.mark.asyncio
    async def test_non_mock_collects_tool_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_execute(
            tool_name: str, *, keyword: str | None = None, tool_mode: Any = None, **kwargs: Any
        ):
            return {
                "platform": "weibo",
                "keyword": keyword,
                "items": [{"title": "live"}],
                "source": "mock",
            }

        monkeypatch.setattr("forge_agent.core.templates.tool_agent.execute_tool", _fake_execute)

        async def _fake_chat(*args: Any, **kwargs: Any) -> Any:
            class _Resp:
                content = (
                    '{"verdict":"lean_positive","confidence":0.7,"risk":0.2,'
                    '"evidence":["tool"],"recommended_action":"watch","metrics":{}}'
                )

            return _Resp()

        monkeypatch.setattr("forge_agent.llm.protocol.chat", _fake_chat)

        agent = ToolAgent(
            {
                "mock_mode": False,
                "platform": "weibo",
                "tools": ["weibo.hot_search"],
                "tool_mode": "mock",
                "prompt": "Analyze {data}",
                "variables": {"keyword": "keyword"},
                "output_mapping": {
                    "verdict": "verdict",
                    "confidence": "confidence",
                    "risk": "risk",
                    "evidence": "evidence",
                    "recommended_action": "recommended_action",
                },
            }
        )
        ctx = AgentContext(
            scope_id="run", scope_name="Run", domain="generic", payload={"keyword": "labubu"}
        )
        report = await agent.run(ctx)
        assert report.raw["data"]["source"] == "mock"
        assert report.raw["data"]["items"][0]["title"] == "live"
