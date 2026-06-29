"""Tests for the LLM-backed ChiefAgent synthesis and guardrails."""

from __future__ import annotations

from typing import Any

import pytest

from forge_agent.builtin.chief_agent import ChiefAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict


def _make_report(
    *,
    agent_id: str = "test.agent",
    verdict: Verdict = Verdict.LEAN_POSITIVE,
    confidence: float = 0.7,
    risk: float = 0.2,
    weight: float = 1.0,
    evidence: list[str] | None = None,
    recommended_action: Action = Action.EXECUTE,
) -> AgentReport:
    return AgentReport(
        agent_id=agent_id,
        name=agent_id,
        domain="sports",
        verdict=verdict,
        confidence=confidence,
        risk=risk,
        weight=weight,
        evidence=evidence or ["sample evidence"],
        recommended_action=recommended_action,
        raw={},
        run_id="r1",
        timestamp="",
        version="0.1.0",
    )


@pytest.mark.anyio()
async def test_chief_weighted_vote_default() -> None:
    agent = ChiefAgent()
    reports = [
        _make_report(verdict=Verdict.LEAN_POSITIVE, confidence=0.8, risk=0.2, weight=2.0),
        _make_report(verdict=Verdict.LEAN_NEGATIVE, confidence=0.6, risk=0.3, weight=1.0),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 2}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert decision["strategy"] == "weighted_vote"
    assert decision["verdict"] == "lean_positive"
    assert decision["confidence"] == pytest.approx(0.70)
    assert decision["risk"] == pytest.approx(0.25)
    assert decision["recommended_action"] == "execute"


@pytest.mark.anyio()
async def test_chief_no_reports() -> None:
    agent = ChiefAgent()
    decision = await agent.decide(None, {"reports": [], "n_reports": 0})  # type: ignore[arg-type]
    assert decision["verdict"] == "neutral"
    assert decision["confidence"] == 0.0
    assert decision["recommended_action"] == "watch"


@pytest.mark.anyio()
async def test_chief_hard_risk_downgrade() -> None:
    agent = ChiefAgent({"hard_risk_threshold": 0.6})
    reports = [
        _make_report(verdict=Verdict.LEAN_POSITIVE, confidence=0.9, risk=0.8, weight=1.0),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 1}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert decision["recommended_action"] == "execute_cautious"
    assert any("hard risk" in g for g in decision["hard_guards"])


@pytest.mark.anyio()
async def test_chief_llm_mock_mode() -> None:
    mock_response = (
        '{"verdict": "lean_positive", "confidence": 0.85, "risk": 0.15, '
        '"recommended_action": "execute", "summary": "LLM summary", '
        '"evidence": ["e1"], "warnings": ["w1"]}'
    )
    agent = ChiefAgent(
        {
            "llm_mode": True,
            "mock_mode": True,
            "mock_response": mock_response,
        }
    )
    reports = [
        _make_report(verdict=Verdict.LEAN_POSITIVE, confidence=0.7, risk=0.2),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 1}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert decision["strategy"] == "llm_synthesis"
    assert decision["verdict"] == "lean_positive"
    assert decision["confidence"] == pytest.approx(0.85)
    assert decision["summary"] == "LLM summary"
    assert decision["evidence"] == ["e1"]


@pytest.mark.anyio()
async def test_chief_llm_mock_downgrade_with_hard_guard() -> None:
    """Even if LLM returns execute, hard guard must downgrade to cautious."""
    mock_response = (
        '{"verdict": "lean_positive", "confidence": 0.9, "risk": 0.1, '
        '"recommended_action": "execute", "summary": "", "evidence": []}'
    )
    agent = ChiefAgent(
        {
            "hard_risk_threshold": 0.5,
            "llm_mode": True,
            "mock_mode": True,
            "mock_response": mock_response,
        }
    )
    reports = [
        _make_report(verdict=Verdict.LEAN_POSITIVE, confidence=0.9, risk=0.6),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 1}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert decision["recommended_action"] == "execute_cautious"
    assert "downgraded" in " ".join(decision.get("warnings", [])).lower()


@pytest.mark.anyio()
async def test_chief_llm_parse_falls_back() -> None:
    agent = ChiefAgent(
        {
            "llm_mode": True,
            "mock_mode": True,
            "mock_response": "not valid json",
        }
    )
    reports = [
        _make_report(verdict=Verdict.LEAN_NEUTRAL, confidence=0.5, risk=0.2),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 1}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert decision["strategy"] == "weighted_vote"
    assert "llm_parse_error" in decision


@pytest.mark.anyio()
async def test_chief_guard_rules_by_agent_and_risk() -> None:
    agent = ChiefAgent(
        {
            "guard_rules": [
                {
                    "name": "odds_suspicious",
                    "description": "赔率专家风险过高",
                    "condition": {"agent_id": "sports.odds", "min_risk": 0.5},
                    "message": "{agent_id} 赔率风险 {risk:.2f} 超过阈值",
                    "level": "error",
                }
            ]
        }
    )
    reports = [
        _make_report(
            agent_id="sports.news", verdict=Verdict.LEAN_POSITIVE, confidence=0.8, risk=0.2
        ),
        _make_report(
            agent_id="sports.odds", verdict=Verdict.LEAN_NEGATIVE, confidence=0.7, risk=0.6
        ),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 2}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert any("sports.odds 赔率风险 0.60" in g for g in decision["hard_guards"])
    # Weighted verdict is lean_positive because sports.news has higher confidence,
    # but the configured guard rule still triggers and downgrades to cautious.
    assert decision["recommended_action"] == "execute_cautious"


@pytest.mark.anyio()
async def test_chief_guard_rules_downgrade_llm_execute() -> None:
    mock_response = (
        '{"verdict": "lean_positive", "confidence": 0.9, "risk": 0.1, '
        '"recommended_action": "execute", "summary": "", "evidence": []}'
    )
    agent = ChiefAgent(
        {
            "llm_mode": True,
            "mock_mode": True,
            "mock_response": mock_response,
            "guard_rules": [
                {
                    "name": "data_insufficient",
                    "condition": {"verdicts": ["risk"], "min_risk": 0.7},
                    "message": "data insufficient for {agent_id}",
                }
            ],
        }
    )
    reports = [
        _make_report(agent_id="sports.odds", verdict=Verdict.RISK, confidence=0.5, risk=0.8),
    ]
    observation: dict[str, Any] = {"reports": [r.to_dict() for r in reports], "n_reports": 1}
    decision = await agent.decide(None, observation)  # type: ignore[arg-type]

    assert decision["strategy"] == "llm_synthesis"
    assert any("data insufficient" in g for g in decision["hard_guards"])
    assert decision["recommended_action"] == "execute_cautious"
