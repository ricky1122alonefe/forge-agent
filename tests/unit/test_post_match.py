"""Tests for post-match feedback / review / evolution."""

from __future__ import annotations

import pytest

from forge_agent.core.capabilities import InMemoryStore
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.report_store import SQLiteReportStore
from forge_agent.learning import MatchOutcome, PostMatchFeedback, PostMatchReflector


@pytest.fixture
def tmp_stores(tmp_path):
    report_store = SQLiteReportStore(db_path=tmp_path / "reports.db")
    outcome_store = InMemoryStore()
    return report_store, outcome_store


@pytest.mark.anyio
async def test_reflector_correct_winner(tmp_stores):
    report = AgentReport(
        agent_id="football.home_expert",
        name="Home Expert",
        domain="football",
        verdict=Verdict.LEAN_POSITIVE,
        confidence=0.75,
        risk=0.3,
        weight=1.0,
        recommended_action=Action.EXECUTE,
        evidence=["home form strong", "key defender back"],
        run_id="match-1",
    )
    outcome = MatchOutcome(actual_winner="home", home_score=2, away_score=1)
    reflector = PostMatchReflector()
    signal = await reflector.reflect("football.home_expert", report, outcome)
    assert signal["score"] > 0.7
    assert any("correct winner" in n for n in signal["notes"])


@pytest.mark.anyio
async def test_reflector_wrong_winner_high_confidence(tmp_stores):
    report = AgentReport(
        agent_id="football.home_expert",
        name="Home Expert",
        domain="football",
        verdict=Verdict.LEAN_POSITIVE,
        confidence=0.9,
        risk=0.1,
        weight=1.0,
        recommended_action=Action.EXECUTE,
        evidence=["sure home win"],
        run_id="match-2",
    )
    outcome = MatchOutcome(actual_winner="away", home_score=0, away_score=2)
    reflector = PostMatchReflector()
    signal = await reflector.reflect("football.home_expert", report, outcome)
    assert signal["score"] < 0.4
    assert signal["needs_evolve"] is True
    assert any("high confidence wrong" in n for n in signal["notes"])


@pytest.mark.anyio
async def test_reflector_exact_scoreline_bonus(tmp_stores):
    report = AgentReport(
        agent_id="football.score_expert",
        name="Score Expert",
        domain="football",
        verdict=Verdict.NEUTRAL,
        confidence=0.6,
        risk=0.4,
        weight=1.0,
        recommended_action=Action.WATCH,
        evidence=["predicted scoreline 2-1"],
        run_id="match-3",
    )
    outcome = MatchOutcome(actual_winner="home", home_score=2, away_score=1)
    reflector = PostMatchReflector()
    signal = await reflector.reflect("football.score_expert", report, outcome)
    assert any("exact scoreline" in n for n in signal["notes"])


@pytest.mark.anyio
async def test_feedback_record_and_review(tmp_stores):
    report_store, outcome_store = tmp_stores
    report = AgentReport(
        agent_id="football.home_expert",
        name="Home Expert",
        domain="football",
        verdict=Verdict.LEAN_POSITIVE,
        confidence=0.8,
        risk=0.2,
        weight=1.0,
        recommended_action=Action.EXECUTE,
        evidence=["home win predicted"],
        run_id="match-4",
    )
    report_store.insert(report)

    feedback = PostMatchFeedback(
        report_store=report_store,
        outcome_store=outcome_store,
    )
    outcome = MatchOutcome(actual_winner="home", home_score=2, away_score=0)
    await feedback.record_outcome("match-4", outcome)

    review = await feedback.review("football.home_expert", "match-4")
    assert review["reflected"] is True
    assert review["signal"]["score"] > 0.7


@pytest.mark.anyio
async def test_feedback_review_without_outcome(tmp_stores):
    report_store, outcome_store = tmp_stores
    feedback = PostMatchFeedback(report_store=report_store, outcome_store=outcome_store)
    result = await feedback.review("football.home_expert", "no-such-run")
    assert result["reflected"] is False
    assert "outcome not recorded" in result["reason"]


@pytest.mark.anyio
async def test_feedback_evolve_triggered(tmp_stores):
    report_store, outcome_store = tmp_stores
    report = AgentReport(
        agent_id="football.bad_expert",
        name="Bad Expert",
        domain="football",
        verdict=Verdict.LEAN_POSITIVE,
        confidence=0.95,
        risk=0.05,
        weight=1.0,
        recommended_action=Action.EXECUTE,
        evidence=["sure home win"],
        run_id="match-5",
    )
    report_store.insert(report)

    from forge_agent.core.capabilities import InMemoryPromptManager

    prompt_manager = InMemoryPromptManager()
    prompt_manager.register("football.bad_expert", "v1", "Predict the winner.")

    feedback = PostMatchFeedback(
        report_store=report_store,
        outcome_store=outcome_store,
    )
    await feedback.record_outcome(
        "match-5",
        MatchOutcome(actual_winner="away", home_score=0, away_score=3),
    )
    result = await feedback.review_and_evolve(
        "football.bad_expert",
        "match-5",
        prompt_manager=prompt_manager,
    )
    assert result["reflected"] is True
    assert result["evolution"] is not None
    assert result["evolution"]["evolved"] is True
    assert result["evolution"]["new_version"] == "v2"
