"""Tests for the constraint engine and BaseAgent integration."""

from __future__ import annotations

import pytest

from forge_agent.constraints import ConstraintEngine, ConstraintPolicy, TriggerType
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Verdict


class TestConstraintEngine:
    async def test_output_block(self) -> None:
        engine = ConstraintEngine()
        engine.add_policy(
            ConstraintPolicy(
                id="bad_word",
                name="Bad word blocker",
                trigger=TriggerType.OUTPUT,
                patterns=["稳赢"],
                action="block",
            )
        )
        result = await engine.check_output("这场球稳赢")
        assert not result.allowed
        assert len(result.violations) == 1
        assert result.violations[0].policy_id == "bad_word"

    async def test_output_allow(self) -> None:
        engine = ConstraintEngine()
        engine.add_policy(
            ConstraintPolicy(
                id="bad_word",
                trigger=TriggerType.OUTPUT,
                patterns=["稳赢"],
                action="block",
            )
        )
        result = await engine.check_output("这场球值得观察")
        assert result.allowed
        assert result.violations == []

    async def test_tool_call_block(self) -> None:
        engine = ConstraintEngine()
        engine.add_policy(
            ConstraintPolicy(
                id="no_bet",
                trigger=TriggerType.TOOL_CALL,
                patterns=["bet", "投注"],
                action="block",
            )
        )
        result = await engine.check_tool_call("place_bet", args={"amount": 100})
        assert not result.allowed

    async def test_input_block(self) -> None:
        engine = ConstraintEngine()
        engine.add_policy(
            ConstraintPolicy(
                id="no_minors",
                trigger=TriggerType.INPUT,
                patterns=["未成年人"],
                action="block",
            )
        )
        result = await engine.check_input({"target_audience": "未成年人"})
        assert not result.allowed

    async def test_disabled_policy_ignored(self) -> None:
        engine = ConstraintEngine()
        engine.add_policy(
            ConstraintPolicy(
                id="bad_word",
                trigger=TriggerType.OUTPUT,
                patterns=["稳赢"],
                action="block",
                enabled=False,
            )
        )
        result = await engine.check_output("这场球稳赢")
        assert result.allowed

    async def test_regex_pattern(self) -> None:
        engine = ConstraintEngine()
        engine.add_policy(
            ConstraintPolicy(
                id="regex_test",
                trigger=TriggerType.OUTPUT,
                patterns=[r"\d+%命中"],
                action="block",
            )
        )
        result = await engine.check_output("100%命中")
        assert not result.allowed

    async def test_load_yaml(self, tmp_path) -> None:
        path = tmp_path / "policies.yaml"
        path.write_text(
            """
policies:
  - id: test
    trigger: output
    patterns: ["x"]
    action: block
""",
            encoding="utf-8",
        )
        engine = ConstraintEngine()
        engine.load_yaml(path)
        result = await engine.check_output("xyz")
        assert not result.allowed


class TestBaseAgentConstraintIntegration:
    def _make_agent(self):
        class DemoAgent(BaseAgent):
            agent_id = "test.demo"
            name = "Demo"

            async def observe(self, ctx):
                return {}

            async def decide(self, ctx, obs):
                return {}

            async def act(self, ctx, dec):
                return AgentReport(
                    agent_id=self.agent_id,
                    name=self.name,
                    verdict=Verdict.SAFE,
                    evidence=["这场球稳赢"],
                )

        DemoAgent.__name__ = "DemoAgent"
        return DemoAgent

    @pytest.mark.asyncio
    async def test_output_blocked(self) -> None:
        agent_class = self._make_agent()
        agent = agent_class(
            config={
                "constraints": {
                    "policies": [
                        {
                            "id": "no_guaranteed_win",
                            "trigger": "output",
                            "patterns": ["稳赢"],
                            "action": "block",
                            "severity": "high",
                        }
                    ]
                }
            }
        )
        ctx = AgentContext(scope_id="m1", scope_name="match")
        report = await agent.run(ctx)
        assert report.verdict == Verdict.RISK
        assert report.risk == 1.0
        assert not report.constraint_result["allowed"]
        assert any("稳赢" in w for w in report.warnings)

    @pytest.mark.asyncio
    async def test_no_constraints(self) -> None:
        agent_class = self._make_agent()
        agent = agent_class()
        ctx = AgentContext(scope_id="m1", scope_name="match")
        report = await agent.run(ctx)
        assert report.verdict == Verdict.SAFE
        assert report.constraint_result == {}
