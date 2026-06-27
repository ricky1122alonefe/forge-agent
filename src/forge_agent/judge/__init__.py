"""Judge module — quality evaluation for AgentReport and AgentBoard.

The Judge analyzes agent outputs across multiple dimensions:
- Consistency: do multiple agents agree?
- Confidence calibration: is confidence reasonable?
- Evidence quality: is evidence sufficient?
- Anomaly detection: does output deviate from historical baseline?

Usage::

    from forge_agent.judge import Judge, JudgeReport

    judge = Judge()
    report = judge.judge_report(some_agent_report)
    print(report.score, report.issues)

    board_report = judge.judge_board(agent_board)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import Verdict

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class JudgeIssue:
    """A single issue found by the judge."""

    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.INFO
    agent_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "agent_id": self.agent_id,
            "details": self.details,
        }


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    name: str
    score: float  # 0.0 ~ 1.0
    weight: float = 1.0
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "weight": self.weight,
            "details": self.details,
        }


@dataclass
class JudgeReport:
    """Result of judging an AgentReport or AgentBoard."""

    target_id: str  # agent_id or "board:<scope_id>"
    target_type: str  # "report" or "board"
    score: float = 0.0  # 0.0 ~ 1.0 overall quality
    grade: str = ""  # A/B/C/D/F
    dimensions: list[DimensionScore] = field(default_factory=list)
    issues: list[JudgeIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "score": round(self.score, 3),
            "grade": self.grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "has_critical": self.has_critical,
            "has_warnings": self.has_warnings,
            "metadata": self.metadata,
        }


# ------------------------------------------------------------------ Judge


class Judge:
    """Quality evaluator for agent outputs.

    Evaluates across configurable dimensions with pluggable checkers.
    """

    def __init__(
        self,
        *,
        confidence_low: float = 0.3,
        confidence_high: float = 0.9,
        min_evidence_count: int = 1,
        consistency_threshold: float = 0.6,
    ) -> None:
        self.confidence_low = confidence_low
        self.confidence_high = confidence_high
        self.min_evidence_count = min_evidence_count
        self.consistency_threshold = consistency_threshold

    def judge_report(self, report: AgentReport) -> JudgeReport:
        """Evaluate a single AgentReport."""
        issues: list[JudgeIssue] = []
        dimensions: list[DimensionScore] = []

        # Dimension 1: Confidence calibration
        conf_score, conf_issues = self._check_confidence(report)
        dimensions.append(DimensionScore(
            name="confidence_calibration",
            score=conf_score,
            weight=1.5,
            details=f"confidence={report.confidence:.2f}",
        ))
        issues.extend(conf_issues)

        # Dimension 2: Evidence quality
        ev_score, ev_issues = self._check_evidence(report)
        dimensions.append(DimensionScore(
            name="evidence_quality",
            score=ev_score,
            weight=2.0,
            details=f"evidence_count={len(report.evidence)}",
        ))
        issues.extend(ev_issues)

        # Dimension 3: Completeness
        comp_score, comp_issues = self._check_completeness(report)
        dimensions.append(DimensionScore(
            name="completeness",
            score=comp_score,
            weight=1.0,
        ))
        issues.extend(comp_issues)

        # Dimension 4: Risk consistency
        risk_score, risk_issues = self._check_risk_consistency(report)
        dimensions.append(DimensionScore(
            name="risk_consistency",
            score=risk_score,
            weight=1.5,
            details=f"risk={report.risk:.2f}, verdict={report.verdict.value}",
        ))
        issues.extend(risk_issues)

        # Calculate overall score
        total_weight = sum(d.weight for d in dimensions)
        overall = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight else 0.0

        # Generate recommendations
        recommendations = self._generate_recommendations(dimensions, issues)

        result = JudgeReport(
            target_id=report.agent_id,
            target_type="report",
            score=round(overall, 3),
            grade=self._score_to_grade(overall),
            dimensions=dimensions,
            issues=issues,
            recommendations=recommendations,
            metadata={
                "verdict": report.verdict.value,
                "confidence": report.confidence,
                "risk": report.risk,
            },
        )
        return result

    def judge_board(self, board: AgentBoard) -> JudgeReport:
        """Evaluate an AgentBoard (multi-agent output)."""
        issues: list[JudgeIssue] = []
        dimensions: list[DimensionScore] = []

        # Judge each individual report
        report_judges: list[JudgeReport] = []
        for report in board.agents:
            rj = self.judge_report(report)
            report_judges.append(rj)
            issues.extend(rj.issues)

        # Dimension 1: Consistency across agents
        cons_score, cons_issues = self._check_board_consistency(board)
        dimensions.append(DimensionScore(
            name="cross_agent_consistency",
            score=cons_score,
            weight=2.0,
            details=f"{len(board.agents)} agents",
        ))
        issues.extend(cons_issues)

        # Dimension 2: Coverage (enough agents contributed)
        cov_score = min(1.0, len(board.agents) / 2.0) if board.agents else 0.0
        dimensions.append(DimensionScore(
            name="agent_coverage",
            score=cov_score,
            weight=1.0,
            details=f"{len(board.agents)} agents reported",
        ))

        # Dimension 3: Hard guards
        guard_score = 0.0 if board.hard_guards else 1.0
        dimensions.append(DimensionScore(
            name="hard_guards",
            score=guard_score,
            weight=3.0,
            details=f"{len(board.hard_guards)} violations" if board.hard_guards else "no violations",
        ))
        if board.hard_guards:
            for hg in board.hard_guards:
                issues.append(JudgeIssue(
                    code="HARD_GUARD",
                    message=hg,
                    severity=IssueSeverity.CRITICAL,
                ))

        # Dimension 4: Average individual quality
        if report_judges:
            avg_individual = sum(r.score for r in report_judges) / len(report_judges)
        else:
            avg_individual = 0.0
        dimensions.append(DimensionScore(
            name="individual_quality",
            score=avg_individual,
            weight=1.5,
            details=f"avg_score={avg_individual:.2f}",
        ))

        # Overall
        total_weight = sum(d.weight for d in dimensions)
        overall = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight else 0.0

        recommendations = self._generate_recommendations(dimensions, issues)

        return JudgeReport(
            target_id=f"board:{board.scope_id}",
            target_type="board",
            score=round(overall, 3),
            grade=self._score_to_grade(overall),
            dimensions=dimensions,
            issues=issues,
            recommendations=recommendations,
            metadata={
                "agent_count": len(board.agents),
                "hard_guards": len(board.hard_guards),
                "ok": board.ok,
                "weighted_verdict": board.weighted_verdict().value,
            },
        )

    # ------------------------------------------------------------------ Checkers

    def _check_confidence(self, report: AgentReport) -> tuple[float, list[JudgeIssue]]:
        issues: list[JudgeIssue] = []
        conf = report.confidence

        if conf < self.confidence_low:
            issues.append(JudgeIssue(
                code="LOW_CONFIDENCE",
                message=f"Confidence {conf:.2f} is below threshold {self.confidence_low}",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            ))
            return 0.3, issues

        if conf > self.confidence_high and not report.evidence:
            issues.append(JudgeIssue(
                code="OVERCONFIDENT",
                message=f"High confidence {conf:.2f} but no evidence provided",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            ))
            return 0.4, issues

        return 1.0, issues

    def _check_evidence(self, report: AgentReport) -> tuple[float, list[JudgeIssue]]:
        issues: list[JudgeIssue] = []
        ev_count = len(report.evidence)

        if ev_count < self.min_evidence_count:
            issues.append(JudgeIssue(
                code="INSUFFICIENT_EVIDENCE",
                message=f"Only {ev_count} evidence items (minimum: {self.min_evidence_count})",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            ))
            return 0.2, issues

        # Check for empty/meaningless evidence
        empty_count = sum(1 for e in report.evidence if not e or not e.strip())
        if empty_count > 0:
            issues.append(JudgeIssue(
                code="EMPTY_EVIDENCE",
                message=f"{empty_count} empty evidence entries",
                severity=IssueSeverity.INFO,
                agent_id=report.agent_id,
            ))
            return max(0.5, 1.0 - empty_count * 0.1), issues

        return min(1.0, ev_count / 3.0), issues

    def _check_completeness(self, report: AgentReport) -> tuple[float, list[JudgeIssue]]:
        issues: list[JudgeIssue] = []
        score = 1.0

        if not report.agent_id:
            issues.append(JudgeIssue(
                code="MISSING_AGENT_ID",
                message="Report has no agent_id",
                severity=IssueSeverity.CRITICAL,
            ))
            score -= 0.5

        if not report.name:
            issues.append(JudgeIssue(
                code="MISSING_NAME",
                message="Report has no name",
                severity=IssueSeverity.INFO,
            ))
            score -= 0.1

        if report.confidence == 0.0 and report.verdict != Verdict.NEUTRAL:
            issues.append(JudgeIssue(
                code="ZERO_CONFIDENCE_NON_NEUTRAL",
                message="Zero confidence with non-neutral verdict",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            ))
            score -= 0.3

        return max(0.0, score), issues

    def _check_risk_consistency(self, report: AgentReport) -> tuple[float, list[JudgeIssue]]:
        issues: list[JudgeIssue] = []

        # High risk should correlate with RISK verdict or low confidence
        if report.risk > 0.7 and report.verdict not in (Verdict.RISK, Verdict.LEAN_NEGATIVE):
            issues.append(JudgeIssue(
                code="RISK_VERDICT_MISMATCH",
                message=f"High risk ({report.risk:.2f}) but verdict is {report.verdict.value}",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            ))
            return 0.5, issues

        # Low risk with RISK verdict is suspicious
        if report.risk < 0.2 and report.verdict == Verdict.RISK:
            issues.append(JudgeIssue(
                code="LOW_RISK_RISK_VERDICT",
                message=f"Low risk ({report.risk:.2f}) but verdict is RISK",
                severity=IssueSeverity.INFO,
                agent_id=report.agent_id,
            ))
            return 0.7, issues

        return 1.0, issues

    def _check_board_consistency(
        self, board: AgentBoard
    ) -> tuple[float, list[JudgeIssue]]:
        issues: list[JudgeIssue] = []
        if len(board.agents) < 2:
            return 1.0, issues

        # Check verdict distribution
        verdicts = [a.verdict for a in board.agents]
        unique_verdicts = set(v.value for v in verdicts)

        # If all agents disagree (all different verdicts), that's a concern
        if len(unique_verdicts) == len(verdicts) and len(verdicts) > 2:
            issues.append(JudgeIssue(
                code="TOTAL_DISAGREEMENT",
                message=f"All {len(verdicts)} agents have different verdicts",
                severity=IssueSeverity.WARNING,
            ))
            return 0.3, issues

        # Check if majority agrees
        from collections import Counter
        verdict_counts = Counter(v.value for v in verdicts)
        majority_ratio = verdict_counts.most_common(1)[0][1] / len(verdicts)

        if majority_ratio < self.consistency_threshold:
            issues.append(JudgeIssue(
                code="LOW_CONSENSUS",
                message=f"Majority agreement is {majority_ratio:.0%} (threshold: {self.consistency_threshold:.0%})",
                severity=IssueSeverity.WARNING,
            ))
            return majority_ratio, issues

        return min(1.0, majority_ratio + 0.2), issues

    # ------------------------------------------------------------------ Helpers

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 0.9:
            return "A"
        if score >= 0.8:
            return "B"
        if score >= 0.6:
            return "C"
        if score >= 0.4:
            return "D"
        return "F"

    @staticmethod
    def _generate_recommendations(
        dimensions: list[DimensionScore],
        issues: list[JudgeIssue],
    ) -> list[str]:
        recs: list[str] = []
        for d in dimensions:
            if d.score < 0.5:
                recs.append(f"Improve '{d.name}' (current: {d.score:.2f})")
        critical = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        if critical:
            recs.append(f"Fix {len(critical)} critical issue(s) before deployment")
        return recs
