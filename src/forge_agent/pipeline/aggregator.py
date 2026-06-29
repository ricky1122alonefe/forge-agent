"""Aggregator: turn a list of AgentReports into an AgentBoard (or domain-specific output).

The default Aggregator is intentionally simple: weighted-majority verdict.
Replace with a Chief Agent (LLM-based) for sophisticated synthesis.
"""

from __future__ import annotations

from datetime import datetime, timezone

from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import Verdict


class Aggregator:
    """Default aggregator: weighted vote + hard-risk guards."""

    def __init__(self, *, hard_risk_threshold: float = 0.7) -> None:
        self.hard_risk_threshold = hard_risk_threshold

    def aggregate(
        self,
        reports: list[AgentReport],
        ctx: AgentContext,
    ) -> AgentBoard:
        hard_guards: list[str] = []
        for r in reports:
            if r.is_hard_risk(self.hard_risk_threshold):
                hard_guards.append(
                    f"{r.agent_id} triggered hard risk ({r.risk:.2f} >= {self.hard_risk_threshold})"
                )

        board = AgentBoard(
            ok=not hard_guards,
            scope_id=ctx.scope_id,
            scope_name=ctx.scope_name,
            generated_at=datetime.now(timezone.utc).isoformat(),
            domain=ctx.domain,
            agents=list(reports),
            hard_guards=hard_guards,
            summary={
                "n_agents": len(reports),
                "total_weight": sum(r.weight for r in reports),
                "avg_confidence": (
                    sum(r.confidence for r in reports) / len(reports) if reports else 0.0
                ),
                "avg_risk": (sum(r.risk for r in reports) / len(reports) if reports else 0.0),
                "weighted_verdict": board_verdict(reports),
            },
        )
        return board


def board_verdict(reports: list[AgentReport]) -> str:
    """Weighted-majority verdict, returned as a string for the summary dict."""
    if not reports:
        return Verdict.NEUTRAL.value
    score: dict[str, float] = {}
    for r in reports:
        score.setdefault(r.verdict.value, 0.0)
        score[r.verdict.value] += r.weight * r.confidence
    return max(score.items(), key=lambda kv: kv[1])[0]
