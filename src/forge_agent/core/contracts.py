"""Standardized output contracts for ALL Agents in forge-agent.

These dataclasses are the **wire format** between Agents, the Scheduler,
the Pipeline, and downstream consumers (Chief, UI, storage).

Rules:
- Every Agent.run() must return an AgentReport.
- A Pipeline's aggregator collects AgentReports into an AgentBoard.
- Do not add business-specific fields here. Domain mapping lives in the Agent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from forge_agent.core.enums import Action, Verdict


@dataclass
class AgentReport:
    """Standardized output of a single Agent run.

    Attributes:
        agent_id:       Globally unique agent identifier (from registry).
        name:           Human-readable name.
        domain:         Business domain tag (e.g. "football", "stock").
        verdict:        Semantic verdict (see Verdict enum).
        confidence:     0.0 ~ 1.0, how confident the agent is.
        risk:           0.0 ~ 1.0, perceived risk (used for hard guards).
        weight:         0.0 ~ N, agent's vote weight in aggregator.
        evidence:       Bullet-point evidence (human-readable strings).
        warnings:       Non-fatal issues encountered.
        recommended_action: Suggested next step (see Action enum).
        metrics:        Free-form quantitative metrics.
        raw:            Free-form raw output (LLM response, etc.).
        run_id:         Unique id of this specific run.
        timestamp:      ISO8601 timestamp.
        version:        Agent version that produced this report.
    """

    agent_id: str
    name: str
    domain: str = "generic"
    verdict: Verdict = Verdict.NEUTRAL
    confidence: float = 0.0
    risk: float = 0.0
    weight: float = 1.0
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_action: Action = Action.WATCH
    metrics: dict[str, float] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    timestamp: str = ""
    version: str = "0.1.0"
    constraint_result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict (verdict/action become strings)."""
        data = asdict(self)
        data["verdict"] = self.verdict.value
        data["recommended_action"] = self.recommended_action.value
        data["confidence"] = round(float(self.confidence), 3)
        data["risk"] = round(float(self.risk), 3)
        data["weight"] = round(float(self.weight), 3)
        return data

    def is_hard_risk(self, threshold: float = 0.7) -> bool:
        """Convenience: did this report cross the hard risk threshold?"""
        return float(self.risk) >= threshold


@dataclass
class AgentBoard:
    """Aggregated board of multiple AgentReports — the Pipeline output.

    Produced by the aggregator (often a Chief Agent), consumed by:
        - downstream Agent runs (next pipeline stage)
        - human review UIs
        - storage / archiving
    """

    ok: bool
    scope_id: str  # e.g. fixture_id, ticker, request_id
    scope_name: str  # human label
    generated_at: str  # ISO8601
    domain: str = "generic"
    agents: list[AgentReport] = field(default_factory=list)
    hard_guards: list[str] = field(default_factory=list)  # hard rule violations
    summary: dict[str, Any] = field(default_factory=dict)
    version: str = "0.1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "scope_id": self.scope_id,
            "scope_name": self.scope_name,
            "generated_at": self.generated_at,
            "domain": self.domain,
            "agents": [a.to_dict() for a in self.agents],
            "hard_guards": self.hard_guards,
            "summary": self.summary,
            "version": self.version,
        }

    def total_weight(self) -> float:
        return sum(float(a.weight) for a in self.agents)

    def weighted_verdict(self) -> Verdict:
        """Naive weighted majority verdict. Aggregators can override."""
        if not self.agents:
            return Verdict.NEUTRAL
        score: dict[str, float] = {}
        for a in self.agents:
            score.setdefault(a.verdict.value, 0.0)
            score[a.verdict.value] += float(a.weight) * float(a.confidence)
        best = max(score.items(), key=lambda kv: kv[1])
        try:
            return Verdict(best[0])
        except ValueError:
            return Verdict.NEUTRAL
