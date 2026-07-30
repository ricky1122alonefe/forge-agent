"""Judge checkers — individual evaluation functions (S6.4 split).

Each checker evaluates one dimension of an AgentReport or AgentBoard
and returns (score, issues). Standalone functions — no state, no
side effects, independently testable.
"""

from __future__ import annotations

from collections import Counter

from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import Verdict
from forge_agent.judge.models import IssueSeverity, JudgeIssue


def check_confidence(
    report: AgentReport, *, confidence_low: float, confidence_high: float
) -> tuple[float, list[JudgeIssue]]:
    issues: list[JudgeIssue] = []
    conf = report.confidence
    if conf is None:
        issues.append(
            JudgeIssue(
                code="MISSING_CONFIDENCE",
                message="Missing confidence; expected a number between 0.0 and 1.0",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        return 0.2, issues

    if conf < confidence_low:
        issues.append(
            JudgeIssue(
                code="LOW_CONFIDENCE",
                message=f"Confidence {conf} is below threshold {confidence_low}",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        return 0.3, issues

    if conf > confidence_high and not report.evidence:
        issues.append(
            JudgeIssue(
                code="OVERCONFIDENT",
                message=f"High confidence {conf} but no evidence provided",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        return 0.4, issues

    return 1.0, issues


def check_evidence(
    report: AgentReport, *, min_evidence_count: int
) -> tuple[float, list[JudgeIssue]]:
    issues: list[JudgeIssue] = []
    ev_count = len(report.evidence)

    if ev_count < min_evidence_count:
        issues.append(
            JudgeIssue(
                code="INSUFFICIENT_EVIDENCE",
                message=f"Only {ev_count} evidence items (minimum: {min_evidence_count})",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        return 0.2, issues

    empty_count = sum(1 for e in report.evidence if not e or not e.strip())
    if empty_count > 0:
        issues.append(
            JudgeIssue(
                code="EMPTY_EVIDENCE",
                message=f"{empty_count} empty evidence entries",
                severity=IssueSeverity.INFO,
                agent_id=report.agent_id,
            )
        )
        return max(0.5, 1.0 - empty_count * 0.1), issues

    return min(1.0, ev_count / 3.0), issues


def check_completeness(report: AgentReport) -> tuple[float, list[JudgeIssue]]:
    issues: list[JudgeIssue] = []
    score = 1.0

    if not report.agent_id:
        issues.append(
            JudgeIssue(
                code="MISSING_AGENT_ID",
                message="Report has no agent_id",
                severity=IssueSeverity.CRITICAL,
            )
        )
        score -= 0.5

    if not report.name:
        issues.append(
            JudgeIssue(
                code="MISSING_NAME",
                message="Report has no name",
                severity=IssueSeverity.INFO,
            )
        )
        score -= 0.1

    if report.confidence == 0.0 and report.verdict != Verdict.NEUTRAL:
        issues.append(
            JudgeIssue(
                code="ZERO_CONFIDENCE_NON_NEUTRAL",
                message="Zero confidence with non-neutral verdict",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        score -= 0.3

    return max(0.0, score), issues


def check_risk_consistency(report: AgentReport) -> tuple[float, list[JudgeIssue]]:
    issues: list[JudgeIssue] = []
    if report.risk is None:
        issues.append(
            JudgeIssue(
                code="MISSING_RISK",
                message="Missing risk; expected a number between 0.0 and 1.0",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        return 0.2, issues

    if report.risk > 0.7 and report.verdict not in (Verdict.RISK, Verdict.LEAN_NEGATIVE):
        issues.append(
            JudgeIssue(
                code="RISK_VERDICT_MISMATCH",
                message=f"High risk ({report.risk}) but verdict is {report.verdict.value}",
                severity=IssueSeverity.WARNING,
                agent_id=report.agent_id,
            )
        )
        return 0.5, issues

    if report.risk < 0.2 and report.verdict == Verdict.RISK:
        issues.append(
            JudgeIssue(
                code="LOW_RISK_RISK_VERDICT",
                message=f"Low risk ({report.risk}) but verdict is RISK",
                severity=IssueSeverity.INFO,
                agent_id=report.agent_id,
            )
        )
        return 0.7, issues

    return 1.0, issues


def check_board_consistency(
    board: AgentBoard, *, consistency_threshold: float
) -> tuple[float, list[JudgeIssue]]:
    issues: list[JudgeIssue] = []
    if len(board.agents) < 2:
        return 1.0, issues

    verdicts = [a.verdict for a in board.agents]
    unique_verdicts = {v.value for v in verdicts}

    if len(unique_verdicts) == len(verdicts) and len(verdicts) > 2:
        issues.append(
            JudgeIssue(
                code="TOTAL_DISAGREEMENT",
                message=f"All {len(verdicts)} agents have different verdicts",
                severity=IssueSeverity.WARNING,
            )
        )
        return 0.3, issues

    verdict_counts = Counter(v.value for v in verdicts)
    majority_ratio = verdict_counts.most_common(1)[0][1] / len(verdicts)

    if majority_ratio < consistency_threshold:
        issues.append(
            JudgeIssue(
                code="LOW_CONSENSUS",
                message=f"Majority agreement is {majority_ratio:.0%} (threshold: {consistency_threshold:.0%})",
                severity=IssueSeverity.WARNING,
            )
        )
        return majority_ratio, issues

    return min(1.0, majority_ratio + 0.2), issues
