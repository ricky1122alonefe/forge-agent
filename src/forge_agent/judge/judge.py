"""Judge — quality evaluator for agent outputs (S6.4 split).

Orchestrates checkers across multiple dimensions to produce a JudgeReport.
Models live in models.py, checkers in checkers.py.
"""

from __future__ import annotations

from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.judge.checkers import (
    check_board_consistency,
    check_completeness,
    check_confidence,
    check_evidence,
    check_risk_consistency,
)
from forge_agent.judge.models import (
    DimensionScore,
    IssueSeverity,
    JudgeIssue,
    JudgeReport,
)


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

        conf_score, conf_issues = check_confidence(
            report,
            confidence_low=self.confidence_low,
            confidence_high=self.confidence_high,
        )
        dimensions.append(
            DimensionScore(
                name="confidence_calibration",
                score=conf_score,
                weight=1.5,
                details=f"confidence={report.confidence if report.confidence is not None else 'n/a'}",
            )
        )
        issues.extend(conf_issues)

        ev_score, ev_issues = check_evidence(report, min_evidence_count=self.min_evidence_count)
        dimensions.append(
            DimensionScore(
                name="evidence_quality",
                score=ev_score,
                weight=2.0,
                details=f"evidence_count={len(report.evidence)}",
            )
        )
        issues.extend(ev_issues)

        comp_score, comp_issues = check_completeness(report)
        dimensions.append(DimensionScore(name="completeness", score=comp_score, weight=1.0))
        issues.extend(comp_issues)

        risk_score, risk_issues = check_risk_consistency(report)
        dimensions.append(
            DimensionScore(
                name="risk_consistency",
                score=risk_score,
                weight=1.5,
                details=f"risk={report.risk if report.risk is not None else 'n/a'}, verdict={report.verdict.value}",
            )
        )
        issues.extend(risk_issues)

        total_weight = sum(d.weight for d in dimensions)
        overall = (
            sum(d.score * d.weight for d in dimensions) / total_weight if total_weight else 0.0
        )

        recommendations = self._generate_recommendations(dimensions, issues)

        return JudgeReport(
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

    def judge_board(self, board: AgentBoard) -> JudgeReport:
        """Evaluate an AgentBoard (multi-agent output)."""
        issues: list[JudgeIssue] = []
        dimensions: list[DimensionScore] = []

        report_judges: list[JudgeReport] = []
        for report in board.agents:
            rj = self.judge_report(report)
            report_judges.append(rj)
            issues.extend(rj.issues)

        cons_score, cons_issues = check_board_consistency(
            board, consistency_threshold=self.consistency_threshold
        )
        dimensions.append(
            DimensionScore(
                name="cross_agent_consistency",
                score=cons_score,
                weight=2.0,
                details=f"{len(board.agents)} agents",
            )
        )
        issues.extend(cons_issues)

        cov_score = min(1.0, len(board.agents) / 2.0) if board.agents else 0.0
        dimensions.append(
            DimensionScore(
                name="agent_coverage",
                score=cov_score,
                weight=1.0,
                details=f"{len(board.agents)} agents reported",
            )
        )

        guard_score = 0.0 if board.hard_guards else 1.0
        dimensions.append(
            DimensionScore(
                name="hard_guards",
                score=guard_score,
                weight=3.0,
                details=f"{len(board.hard_guards)} violations"
                if board.hard_guards
                else "no violations",
            )
        )
        if board.hard_guards:
            for hg in board.hard_guards:
                issues.append(
                    JudgeIssue(
                        code="HARD_GUARD",
                        message=hg,
                        severity=IssueSeverity.CRITICAL,
                    )
                )

        if report_judges:
            avg_individual = sum(r.score for r in report_judges) / len(report_judges)
        else:
            avg_individual = 0.0
        dimensions.append(
            DimensionScore(
                name="individual_quality",
                score=avg_individual,
                weight=1.5,
                details=f"avg_score={avg_individual:.2f}",
            )
        )

        total_weight = sum(d.weight for d in dimensions)
        overall = (
            sum(d.score * d.weight for d in dimensions) / total_weight if total_weight else 0.0
        )

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
