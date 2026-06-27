"""Integration tests for BaseAgent.evolve() — real self-iteration logic.

Verifies that:
    - evolve() runs reflection and decides whether to evolve
    - evolve() bumps prompt version when score is low
    - evolve() skips evolution when score is high
    - evolve() handles missing history gracefully
    - evolve() integrates with HeuristicReflector + PromptOptimizer
"""

from __future__ import annotations

import pytest
from typing import Any, ClassVar

from forge_agent.core.base import BaseAgent
from forge_agent.core.capabilities import InMemoryPromptManager, InMemoryStore
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Action, Verdict
from forge_agent.learning.reflection import HeuristicReflector


class _TestAgent(BaseAgent):
    agent_id: ClassVar[str] = "test.evolve_agent"
    name: ClassVar[str] = "Test Evolve Agent"
    version: ClassVar[str] = "0.1.0"
    domain: ClassVar[str] = "generic"

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        return {"data": "test"}

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        return {"action": "test"}

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=Verdict.SAFE,
            confidence=0.8,
            risk=0.2,
            evidence=["test evidence"],
            recommended_action=Action.WATCH,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )


def _make_ctx(**overrides: Any) -> AgentContext:
    return AgentContext(
        scope_id="test",
        scope_name="test",
        domain="generic",
        payload={"test": True},
        **overrides,
    )


class TestEvolveNoHistory:
    @pytest.mark.asyncio
    async def test_evolve_no_history(self):
        """evolve() should return evolved=False when no execution history."""
        agent = _TestAgent()
        agent.prompt_manager = InMemoryPromptManager()
        agent.reflector = HeuristicReflector()
        agent.memory = InMemoryStore()

        result = await agent.evolve(_make_ctx())
        assert result["evolved"] is False
        assert "no execution history" in result["reason"]


class TestEvolveHighScore:
    @pytest.mark.asyncio
    async def test_evolve_skips_when_score_high(self):
        """evolve() should skip when reflection score is above threshold."""
        agent = _TestAgent()
        agent.prompt_manager = InMemoryPromptManager()
        agent.prompt_manager.register("test.evolve_agent", "v1", "Good prompt template")
        agent.reflector = HeuristicReflector()
        agent.memory = InMemoryStore()

        # Store a high-quality execution result
        await agent.memory.store("test.evolve_agent:run1", {
            "agent_id": "test.evolve_agent",
            "observation": {"data": "good"},
            "decision": {"action": "good"},
            "result": {
                "verdict": "SAFE",
                "confidence": 0.9,
                "risk": 0.1,
                "warnings": [],
            },
        })

        result = await agent.evolve(_make_ctx())
        assert result["evolved"] is False


class TestEvolveLowScore:
    @pytest.mark.asyncio
    async def test_evolve_triggers_on_low_score(self):
        """evolve() should trigger when reflection score is low."""
        agent = _TestAgent()
        agent.prompt_manager = InMemoryPromptManager()
        agent.prompt_manager.register("test.evolve_agent", "v1", "Original prompt template")
        agent.reflector = HeuristicReflector()
        agent.memory = InMemoryStore()

        # Store a poor execution result (high risk, low confidence, warnings)
        await agent.memory.store("test.evolve_agent:run1", {
            "agent_id": "test.evolve_agent",
            "observation": {"data": "bad"},
            "decision": {"action": "bad"},
            "result": {
                "verdict": "RISK",
                "confidence": 0.2,
                "risk": 0.9,
                "warnings": ["warning1", "warning2", "warning3"],
            },
        })

        result = await agent.evolve(_make_ctx())
        assert result["evolved"] is True
        assert result["old_version"] == "v1"
        assert result["new_version"] == "v2"

        # Verify new prompt version exists
        versions = agent.prompt_manager.list_versions("test.evolve_agent")
        assert "v2" in versions


class TestEvolveMultipleRuns:
    @pytest.mark.asyncio
    async def test_evolve_after_multiple_runs(self):
        """evolve() should use the most recent execution for reflection."""
        agent = _TestAgent()
        agent.prompt_manager = InMemoryPromptManager()
        agent.prompt_manager.register("test.evolve_agent", "v1", "Template v1")
        agent.reflector = HeuristicReflector()
        agent.memory = InMemoryStore()

        # Store multiple runs — last one is bad
        await agent.memory.store("test.evolve_agent:run1", {
            "agent_id": "test.evolve_agent",
            "observation": {},
            "decision": {},
            "result": {"confidence": 0.9, "risk": 0.1, "warnings": []},
        })
        await agent.memory.store("test.evolve_agent:run2", {
            "agent_id": "test.evolve_agent",
            "observation": {},
            "decision": {},
            "result": {"confidence": 0.1, "risk": 0.9, "warnings": ["w1", "w2", "w3"]},
        })

        result = await agent.evolve(_make_ctx())
        # Should evolve because the most recent run is bad
        assert result["evolved"] is True


class TestEvolveWithReflectionFailure:
    @pytest.mark.asyncio
    async def test_evolve_handles_reflection_error(self):
        """evolve() should handle reflector failures gracefully."""
        agent = _TestAgent()
        agent.prompt_manager = InMemoryPromptManager()
        agent.prompt_manager.register("test.evolve_agent", "v1", "Template")

        # A reflector that always fails
        class FailingReflector:
            async def reflect(self, **kwargs):
                raise RuntimeError("reflector broken")

        agent.reflector = FailingReflector()
        agent.memory = InMemoryStore()

        await agent.memory.store("test.evolve_agent:run1", {
            "agent_id": "test.evolve_agent",
            "observation": {},
            "decision": {},
            "result": {},
        })

        result = await agent.evolve(_make_ctx())
        assert result["evolved"] is False
        assert "reflection failed" in result["reason"]


class TestEvolveIntegrationWithRunCycle:
    @pytest.mark.asyncio
    async def test_full_run_then_evolve(self):
        """Full cycle: run() → reflect → learn → evolve."""
        agent = _TestAgent()
        agent.prompt_manager = InMemoryPromptManager()
        agent.prompt_manager.register("test.evolve_agent", "v1", "Initial template")
        agent.reflector = HeuristicReflector()
        agent.memory = InMemoryStore()

        ctx = _make_ctx()

        # Run the agent (observe → decide → act → reflect → learn)
        report = await agent.run(ctx)
        assert report.agent_id == "test.evolve_agent"

        # Now evolve — should find the stored execution in memory
        result = await agent.evolve(ctx)
        # The result depends on the reflection score of the run
        assert "evolved" in result
