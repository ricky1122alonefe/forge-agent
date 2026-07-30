"""Judge module — quality evaluation for AgentReport and AgentBoard.

S6.4 split: models → models.py, checkers → checkers.py, Judge → judge.py.
This __init__ re-exports the public API for backward compatibility.

Usage::

    from forge_agent.judge import Judge, JudgeReport

    judge = Judge()
    report = judge.judge_report(some_agent_report)
    print(report.score, report.issues)

    board_report = judge.judge_board(agent_board)
"""

from __future__ import annotations

from forge_agent.judge.checkers import (
    check_board_consistency,
    check_completeness,
    check_confidence,
    check_evidence,
    check_risk_consistency,
)
from forge_agent.judge.judge import Judge
from forge_agent.judge.models import (
    DimensionScore,
    IssueSeverity,
    JudgeIssue,
    JudgeReport,
)

__all__ = [
    "DimensionScore",
    "IssueSeverity",
    "Judge",
    "JudgeIssue",
    "JudgeReport",
    "check_board_consistency",
    "check_completeness",
    "check_confidence",
    "check_evidence",
    "check_risk_consistency",
]
