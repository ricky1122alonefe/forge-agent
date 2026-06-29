"""Post-match feedback loop for predictive agents (sports, finance, etc.).

Provides:
    - MatchOutcome: a small dataclass describing the actual outcome.
    - PostMatchReflector: compares a past AgentReport with the actual outcome
      and produces a ReflectionSignal.
    - PostMatchFeedback: high-level helper that loads a stored report,
      records the outcome, reflects, and (optionally) evolves the agent.

Typical flow after a fixture finishes::

    from forge_agent.learning.post_match import MatchOutcome, PostMatchFeedback

    feedback = PostMatchFeedback()
    await feedback.record_outcome(
        run_id="fixture-123",
        outcome=MatchOutcome(actual_winner="home", home_score=2, away_score=1),
    )
    result = await feedback.review_and_evolve("football.home_expert", "fixture-123")
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from forge_agent.core.capabilities import InMemoryStore
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.report_store import SQLiteReportStore
from forge_agent.learning.optimizer import PromptOptimizer
from forge_agent.learning.reflection import ReflectionSignal

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MatchOutcome:
    """Actual outcome of a predicted event.

    Attributes:
        actual_winner: "home" | "away" | "draw" for sports, or any domain label.
        home_score: Optional numeric score for the home side.
        away_score: Optional numeric score for the away side.
        notes: Free-form notes (e.g. key events, weather, red cards).
        metadata: Arbitrary structured metadata.
    """

    actual_winner: str = ""
    home_score: float | None = None
    away_score: float | None = None
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatchOutcome:
        return cls(
            actual_winner=data.get("actual_winner", ""),
            home_score=data.get("home_score"),
            away_score=data.get("away_score"),
            notes=list(data.get("notes", [])),
            metadata=dict(data.get("metadata", {})),
        )


class PostMatchReflector:
    """Rule-based reflector that scores an AgentReport against the actual outcome."""

    def __init__(self, *, correct_score_bonus: float = 0.2) -> None:
        self.correct_score_bonus = correct_score_bonus

    async def reflect(
        self,
        agent_id: str,
        report: AgentReport,
        outcome: MatchOutcome,
    ) -> dict[str, Any]:
        """Produce a ReflectionSignal by comparing prediction to reality.

        Scoring heuristics:
            - Predicted winner matches actual winner: big positive.
            - Predicted winner wrong: big negative.
            - Confidence calibration: over-confident wrong answers are penalized
              more than low-confidence wrong answers.
            - Correct scoreline: small bonus.
        """
        notes: list[str] = []
        score = 0.5

        predicted_winner = self._extract_predicted_winner(report)
        actual_winner = outcome.actual_winner.lower().strip()

        if predicted_winner and actual_winner:
            if predicted_winner == actual_winner:
                score += 0.35
                notes.append(f"correct winner prediction ({predicted_winner})")
            else:
                score -= 0.35
                notes.append(f"wrong winner: predicted {predicted_winner}, actual {actual_winner}")

            # Confidence calibration penalty/bonus
            confidence = float(report.confidence)
            if predicted_winner == actual_winner:
                if confidence >= 0.8:
                    score += 0.05
                    notes.append("high confidence correct")
            else:
                if confidence >= 0.8:
                    score -= 0.15
                    notes.append("high confidence wrong prediction")
                elif confidence <= 0.4:
                    score += 0.05
                    notes.append("low confidence wrong prediction (well calibrated)")

        # Scoreline bonus
        if outcome.home_score is not None and outcome.away_score is not None:
            pred_home, pred_away = self._extract_predicted_score(report)
            if pred_home is not None and pred_away is not None:
                if pred_home == outcome.home_score and pred_away == outcome.away_score:
                    score += self.correct_score_bonus
                    notes.append("exact scoreline predicted")
                else:
                    notes.append(
                        f"scoreline off: predicted {pred_home}-{pred_away}, "
                        f"actual {outcome.home_score}-{outcome.away_score}"
                    )

        if outcome.notes:
            notes.extend(outcome.notes[:3])

        score = max(0.0, min(1.0, score))

        signal = ReflectionSignal(
            agent_id=agent_id,
            score=score,
            notes=notes or ["no outcome comparison possible"],
            needs_evolve=score < 0.4,
            suggested_prompt_diff={
                "add": (
                    "Incorporate the post-match correction: "
                    f"actual winner was {actual_winner}. "
                    "Re-evaluate which signals drove the wrong conclusion."
                )
                if score < 0.5
                else "",
            },
        )
        return signal.to_dict()

    @staticmethod
    def _extract_predicted_winner(report: AgentReport) -> str | None:
        """Best-effort extraction of predicted winner from a report."""
        # Check explicit recommendation first.
        action = report.recommended_action
        if action in (Action.EXECUTE, Action.EXECUTE_CAUTIOUS):
            return "home"
        if action in (Action.STOP, Action.ALERT, Action.ESCALATE):
            return "away"

        # Check verdict heuristics.
        verdict = report.verdict
        if verdict in (Verdict.LEAN_POSITIVE, Verdict.SAFE, Verdict.OK):
            return "home"
        if verdict in (Verdict.LEAN_NEGATIVE, Verdict.RISK):
            return "away"
        if verdict in (Verdict.LEAN_NEUTRAL, Verdict.NEUTRAL):
            return "draw"

        # Fallback: scan evidence for keywords.
        text = " ".join(report.evidence).lower()
        if "home win" in text or "主队胜" in text:
            return "home"
        if "away win" in text or "客队胜" in text:
            return "away"
        if "draw" in text or "平局" in text:
            return "draw"
        return None

    @staticmethod
    def _extract_predicted_score(report: AgentReport) -> tuple[float | None, float | None]:
        """Best-effort extraction of a predicted scoreline."""
        text = " ".join(report.evidence)
        import re

        # Look for patterns like "2-1", "2:1", "2 - 1"
        match = re.search(r"(\d+(?:\.\d+)?)\s*[-:]\s*(\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None


class PostMatchFeedback:
    """High-level helper: record outcomes and trigger agent evolution."""

    def __init__(
        self,
        *,
        report_store: SQLiteReportStore | None = None,
        outcome_store: InMemoryStore | None = None,
        reflector: PostMatchReflector | None = None,
        llm_chat: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
    ) -> None:
        self.report_store = report_store or SQLiteReportStore()
        self.outcome_store = outcome_store or InMemoryStore()
        self.reflector = reflector or PostMatchReflector()
        self.llm_chat = llm_chat

    async def record_outcome(
        self,
        run_id: str,
        outcome: MatchOutcome,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist the actual outcome for a given run_id."""
        report = self.report_store.get_by_run_id(run_id)
        effective_agent_id = agent_id or (report.agent_id if report else "unknown")

        record = {
            "run_id": run_id,
            "agent_id": effective_agent_id,
            "outcome": outcome.to_dict(),
            "recorded_at": _now_iso(),
        }
        await self.outcome_store.store(
            key=f"outcome:{run_id}",
            value=record,
        )
        log.info(
            "PostMatchFeedback: recorded outcome for run_id=%s agent=%s", run_id, effective_agent_id
        )
        return record

    async def review(
        self,
        agent_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Reflect on a single historical run given the recorded outcome."""
        outcome_data = await self.outcome_store.retrieve(f"outcome:{run_id}")
        if outcome_data is None:
            return {"reflected": False, "reason": f"outcome not recorded for run_id={run_id}"}

        report = self.report_store.get_by_run_id(run_id)
        if report is None:
            return {"reflected": False, "reason": f"report not found for run_id={run_id}"}

        outcome = MatchOutcome.from_dict(outcome_data.get("outcome", {}))
        signal = await self.reflector.reflect(agent_id, report, outcome)
        return {
            "reflected": True,
            "run_id": run_id,
            "agent_id": agent_id,
            "signal": signal,
        }

    async def review_and_evolve(
        self,
        agent_id: str,
        run_id: str,
        *,
        prompt_manager: Any | None = None,
        evolve_threshold: float = 0.4,
    ) -> dict[str, Any]:
        """Full post-match cycle: load report + outcome, reflect, and evolve if needed."""
        review_result = await self.review(agent_id, run_id)
        if not review_result["reflected"]:
            return review_result

        signal = review_result["signal"]

        # Evolve if a prompt manager is provided.
        evolution: dict[str, Any] | None = None
        if prompt_manager is not None:
            optimizer = PromptOptimizer(
                prompt_manager=prompt_manager,
                evolve_threshold=evolve_threshold,
                llm_chat=self.llm_chat,
            )
            if optimizer.should_evolve(signal):
                evolution = await optimizer.evolve(agent_id, signal)
                log.info(
                    "PostMatchFeedback: evolved %s after review -> %s",
                    agent_id,
                    evolution.get("new_version", "unchanged"),
                )

        return {
            "reflected": True,
            "run_id": run_id,
            "agent_id": agent_id,
            "signal": signal,
            "evolution": evolution,
        }
