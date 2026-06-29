"""Tests for PromptOptimizer — enhanced with evolution, trend analysis, LLM-driven improvement."""

from __future__ import annotations

import pytest

from forge_agent.core.capabilities import InMemoryPromptManager
from forge_agent.learning.optimizer import EvolutionRecord, PromptOptimizer


@pytest.fixture
def pm():
    return InMemoryPromptManager()


@pytest.fixture
def opt(pm):
    return PromptOptimizer(prompt_manager=pm)


@pytest.fixture
def opt_llm(pm):
    async def mock_chat(messages, **kwargs):
        return "Improved prompt template with better instructions."

    return PromptOptimizer(prompt_manager=pm, llm_chat=mock_chat)


# ------------------------------------------------------------------ should_evolve


class TestShouldEvolve:
    def test_needs_evolve_flag(self, opt):
        assert opt.should_evolve({"needs_evolve": True, "score": 0.9}) is True

    def test_low_score(self, opt):
        assert opt.should_evolve({"score": 0.1}) is True

    def test_high_score_no_evolve(self, opt):
        assert opt.should_evolve({"score": 0.9, "needs_evolve": False}) is False

    def test_exact_threshold(self, opt):
        # score == threshold → not below → no evolve (unless needs_evolve)
        assert opt.should_evolve({"score": 0.3}) is False

    def test_just_below_threshold(self, opt):
        assert opt.should_evolve({"score": 0.29}) is True

    def test_custom_threshold(self, pm):
        opt = PromptOptimizer(prompt_manager=pm, evolve_threshold=0.5)
        assert opt.should_evolve({"score": 0.4}) is True
        assert opt.should_evolve({"score": 0.6}) is False

    def test_declining_trend_triggers_evolve(self, opt):
        """Declining trend + score < 0.5 should trigger evolve."""
        # Record declining history
        for i in range(5):
            opt.record_reflection({"agent_id": "test.agent", "score": 0.2 - i * 0.01})
        # Now check with a mediocre score
        assert opt.should_evolve({"agent_id": "test.agent", "score": 0.4}) is True

    def test_missing_score_defaults_to_no_evolve(self, opt):
        assert opt.should_evolve({}) is False


# ------------------------------------------------------------------ bump_version


class TestBumpVersion:
    def test_auto_increment(self, opt, pm):
        pm.register("test.agent", "v1", "template v1")
        v = opt.bump_version("test.agent", "template v2")
        assert v == "v2"
        assert pm.get("test.agent", version="v2") == "template v2"

    def test_explicit_version(self, opt, pm):
        pm.register("test.agent", "v1", "template v1")
        v = opt.bump_version("test.agent", "custom", version="v-custom")
        assert v == "v-custom"

    def test_first_version(self, opt, pm):
        v = opt.bump_version("new.agent", "first template")
        assert v == "v1"

    def test_multiple_increments(self, opt, pm):
        opt.bump_version("test.agent", "v1")
        opt.bump_version("test.agent", "v2")
        v = opt.bump_version("test.agent", "v3")
        assert v == "v3"
        assert len(pm.list_versions("test.agent")) == 3


# ------------------------------------------------------------------ record_reflection & analyze_trend


class TestTrendAnalysis:
    def test_no_history(self, opt):
        trend = opt.analyze_trend("unknown.agent")
        assert trend["trend"] == "stable"
        assert trend["count"] == 0

    def test_single_reflection(self, opt):
        opt.record_reflection({"agent_id": "a", "score": 0.5})
        trend = opt.analyze_trend("a")
        assert trend["count"] == 1
        assert trend["trend"] == "stable"

    def test_improving_trend(self, opt):
        for s in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            opt.record_reflection({"agent_id": "a", "score": s})
        trend = opt.analyze_trend("a")
        assert trend["trend"] == "improving"
        assert trend["declining"] is False

    def test_declining_trend(self, opt):
        for s in [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]:
            opt.record_reflection({"agent_id": "a", "score": s})
        trend = opt.analyze_trend("a")
        assert trend["trend"] == "declining"

    def test_stable_trend(self, opt):
        for s in [0.5, 0.5, 0.5, 0.5]:
            opt.record_reflection({"agent_id": "a", "score": s})
        trend = opt.analyze_trend("a")
        assert trend["trend"] == "stable"

    def test_declining_flag_requires_low_scores(self, opt):
        """declining=True only if last 3 scores are all below threshold."""
        for s in [0.8, 0.7, 0.6, 0.5, 0.4, 0.2, 0.1, 0.1]:
            opt.record_reflection({"agent_id": "a", "score": s})
        trend = opt.analyze_trend("a")
        assert trend["declining"] is True

    def test_max_history_limit(self, pm):
        opt = PromptOptimizer(prompt_manager=pm, max_history=5)
        for _i in range(20):
            opt.record_reflection({"agent_id": "a", "score": 0.5})
        assert len(opt._reflection_history["a"]) == 5


# ------------------------------------------------------------------ evolve


class TestEvolve:
    @pytest.mark.asyncio
    async def test_evolve_no_prompt_registered(self, opt):
        result = await opt.evolve("unknown.agent", {"score": 0.1})
        assert result["evolved"] is False
        assert "no prompt registered" in result["reason"]

    @pytest.mark.asyncio
    async def test_evolve_heuristic(self, opt, pm):
        pm.register("test.agent", "v1", "Original prompt template")
        signal = {"score": 0.2, "notes": ["high risk observed", "low confidence"]}
        result = await opt.evolve("test.agent", signal)
        assert result["evolved"] is True
        assert result["old_version"] == "v1"
        assert result["new_version"] == "v2"
        # New version should contain improvement guidance
        new_prompt = pm.get("test.agent", version="v2")
        assert "Areas to improve" in new_prompt

    @pytest.mark.asyncio
    async def test_evolve_with_llm(self, opt_llm, pm):
        pm.register("test.agent", "v1", "Original prompt")
        signal = {"score": 0.2, "notes": ["needs better analysis"]}
        result = await opt_llm.evolve("test.agent", signal)
        assert result["evolved"] is True
        new_prompt = pm.get("test.agent", version="v2")
        assert "Improved prompt template" in new_prompt

    @pytest.mark.asyncio
    async def test_evolve_no_improvement(self, opt, pm):
        pm.register("test.agent", "v1", "Good prompt")
        signal = {"score": 0.9, "notes": []}
        result = await opt.evolve("test.agent", signal)
        # No notes → heuristic produces same template → no evolution
        assert result["evolved"] is False

    @pytest.mark.asyncio
    async def test_evolve_records_history(self, opt, pm):
        pm.register("test.agent", "v1", "Template v1")
        signal = {"score": 0.1, "notes": ["bad performance"]}
        await opt.evolve("test.agent", signal)
        history = opt.get_history("test.agent")
        assert len(history) == 1
        assert history[0]["old_version"] == "v1"
        assert history[0]["new_version"] == "v2"
        assert history[0]["score_before"] == 0.1

    @pytest.mark.asyncio
    async def test_evolve_multiple_times(self, opt, pm):
        pm.register("test.agent", "v1", "Template v1")
        for i in range(3):
            signal = {"score": 0.1, "notes": [f"issue {i}"]}
            result = await opt.evolve("test.agent", signal)
            assert result["evolved"] is True
        history = opt.get_history("test.agent")
        assert len(history) == 3
        assert len(pm.list_versions("test.agent")) == 4  # v1 + 3 evolutions

    @pytest.mark.asyncio
    async def test_evolve_with_suggested_diff(self, opt, pm):
        pm.register("test.agent", "v1", "Base template")
        signal = {
            "score": 0.2,
            "notes": ["missing error handling"],
            "suggested_prompt_diff": {"add": "Always handle errors gracefully."},
        }
        result = await opt.evolve("test.agent", signal)
        assert result["evolved"] is True
        new_prompt = pm.get("test.agent", version="v2")
        assert "Always handle errors gracefully" in new_prompt


# ------------------------------------------------------------------ EvolutionRecord


class TestEvolutionRecord:
    def test_to_dict(self):
        rec = EvolutionRecord(
            agent_id="test.agent",
            old_version="v1",
            new_version="v2",
            reason="low score",
            score_before=0.2,
            score_after=0.5,
            notes=["improved"],
        )
        d = rec.to_dict()
        assert d["agent_id"] == "test.agent"
        assert d["old_version"] == "v1"
        assert d["score_before"] == 0.2
        assert d["notes"] == ["improved"]


# ------------------------------------------------------------------ get_history


class TestGetHistory:
    def test_empty_history(self, opt):
        assert opt.get_history("unknown") == []

    @pytest.mark.asyncio
    async def test_history_after_evolve(self, opt, pm):
        pm.register("a", "v1", "template")
        await opt.evolve("a", {"score": 0.1, "notes": ["bad"]})
        h = opt.get_history("a")
        assert len(h) == 1
        assert h[0]["agent_id"] == "a"
