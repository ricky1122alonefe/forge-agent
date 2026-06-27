"""Tests for the Judge module (judge/__init__.py)."""

from __future__ import annotations

import pytest

from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.judge import (
    DimensionScore,
    IssueSeverity,
    Judge,
    JudgeIssue,
    JudgeReport,
)


# ------------------------------------------------------------------ Helpers


def _good_report(**overrides) -> AgentReport:
    defaults = dict(
        agent_id="test.agent",
        name="Test Agent",
        domain="generic",
        verdict=Verdict.LEAN_POSITIVE,
        confidence=0.75,
        risk=0.2,
        evidence=["evidence 1", "evidence 2", "evidence 3"],
    )
    defaults.update(overrides)
    return AgentReport(**defaults)


def _bad_report(**overrides) -> AgentReport:
    defaults = dict(
        agent_id="test.bad",
        name="Bad Agent",
        domain="generic",
        verdict=Verdict.RISK,
        confidence=0.1,
        risk=0.9,
        evidence=[],
    )
    defaults.update(overrides)
    return AgentReport(**defaults)


def _board(agents: list[AgentReport] | None = None, **overrides) -> AgentBoard:
    if agents is None:
        agents = [_good_report(), _good_report(agent_id="test.agent2")]
    defaults = dict(
        ok=True,
        scope_id="scope_1",
        scope_name="Test Scope",
        generated_at="2026-01-01T00:00:00Z",
        agents=agents,
    )
    defaults.update(overrides)
    return AgentBoard(**defaults)


# ------------------------------------------------------------------ JudgeIssue / JudgeReport


class TestDataclasses:
    def test_issue_to_dict(self):
        issue = JudgeIssue(code="TEST", message="test msg", severity=IssueSeverity.WARNING)
        d = issue.to_dict()
        assert d["code"] == "TEST"
        assert d["severity"] == "warning"

    def test_dimension_score_to_dict(self):
        ds = DimensionScore(name="conf", score=0.85, weight=1.5)
        d = ds.to_dict()
        assert d["name"] == "conf"
        assert d["score"] == 0.85
        assert d["weight"] == 1.5

    def test_judge_report_has_critical(self):
        jr = JudgeReport(
            target_id="t",
            target_type="report",
            issues=[
                JudgeIssue(code="A", message="a", severity=IssueSeverity.CRITICAL),
                JudgeIssue(code="B", message="b", severity=IssueSeverity.INFO),
            ],
        )
        assert jr.has_critical is True
        assert jr.has_warnings is False

    def test_judge_report_has_warnings(self):
        jr = JudgeReport(
            target_id="t",
            target_type="report",
            issues=[JudgeIssue(code="W", message="w", severity=IssueSeverity.WARNING)],
        )
        assert jr.has_critical is False
        assert jr.has_warnings is True

    def test_judge_report_to_dict(self):
        jr = JudgeReport(target_id="t", target_type="report", score=0.8, grade="B")
        d = jr.to_dict()
        assert d["score"] == 0.8
        assert d["grade"] == "B"
        assert "has_critical" in d


# ------------------------------------------------------------------ Judge.judge_report


class TestJudgeReport:
    def test_good_report_high_score(self):
        judge = Judge()
        report = _good_report()
        result = judge.judge_report(report)
        assert result.score >= 0.7
        assert result.grade in ("A", "B")
        assert result.target_id == "test.agent"
        assert result.target_type == "report"

    def test_bad_report_low_score(self):
        judge = Judge()
        report = _bad_report()
        result = judge.judge_report(report)
        assert result.score < 0.7
        assert len(result.issues) > 0

    def test_low_confidence_warning(self):
        judge = Judge()
        report = _good_report(confidence=0.1)
        result = judge.judge_report(report)
        codes = [i.code for i in result.issues]
        assert "LOW_CONFIDENCE" in codes

    def test_overconfident_no_evidence(self):
        judge = Judge()
        report = _good_report(confidence=0.95, evidence=[])
        result = judge.judge_report(report)
        codes = [i.code for i in result.issues]
        assert "OVERCONFIDENT" in codes or "INSUFFICIENT_EVIDENCE" in codes

    def test_insufficient_evidence(self):
        judge = Judge()
        report = _good_report(evidence=[])
        result = judge.judge_report(report)
        codes = [i.code for i in result.issues]
        assert "INSUFFICIENT_EVIDENCE" in codes

    def test_risk_verdict_mismatch(self):
        judge = Judge()
        report = _good_report(risk=0.85, verdict=Verdict.LEAN_POSITIVE)
        result = judge.judge_report(report)
        codes = [i.code for i in result.issues]
        assert "RISK_VERDICT_MISMATCH" in codes

    def test_dimensions_present(self):
        judge = Judge()
        result = judge.judge_report(_good_report())
        dim_names = [d.name for d in result.dimensions]
        assert "confidence_calibration" in dim_names
        assert "evidence_quality" in dim_names
        assert "completeness" in dim_names
        assert "risk_consistency" in dim_names

    def test_custom_thresholds(self):
        judge = Judge(confidence_low=0.5, min_evidence_count=5)
        report = _good_report(confidence=0.4, evidence=["a", "b"])
        result = judge.judge_report(report)
        codes = [i.code for i in result.issues]
        assert "LOW_CONFIDENCE" in codes
        assert "INSUFFICIENT_EVIDENCE" in codes


# ------------------------------------------------------------------ Judge.judge_board


class TestJudgeBoard:
    def test_good_board(self):
        judge = Judge()
        board = _board()
        result = judge.judge_board(board)
        assert result.target_type == "board"
        assert result.score > 0

    def test_board_with_hard_guards(self):
        judge = Judge()
        board = _board(hard_guards=["Risk too high"])
        result = judge.judge_board(board)
        assert result.has_critical is True
        codes = [i.code for i in result.issues]
        assert "HARD_GUARD" in codes

    def test_board_total_disagreement(self):
        judge = Judge()
        agents = [
            _good_report(agent_id="a1", verdict=Verdict.LEAN_POSITIVE),
            _good_report(agent_id="a2", verdict=Verdict.LEAN_NEGATIVE),
            _good_report(agent_id="a3", verdict=Verdict.RISK),
        ]
        board = _board(agents=agents)
        result = judge.judge_board(board)
        codes = [i.code for i in result.issues]
        assert "TOTAL_DISAGREEMENT" in codes

    def test_board_consensus(self):
        judge = Judge()
        agents = [
            _good_report(agent_id="a1", verdict=Verdict.LEAN_POSITIVE),
            _good_report(agent_id="a2", verdict=Verdict.LEAN_POSITIVE),
            _good_report(agent_id="a3", verdict=Verdict.LEAN_POSITIVE),
        ]
        board = _board(agents=agents)
        result = judge.judge_board(board)
        # Should have good consistency score
        cons_dim = next(d for d in result.dimensions if d.name == "cross_agent_consistency")
        assert cons_dim.score >= 0.8

    def test_empty_board(self):
        judge = Judge()
        board = _board(agents=[])
        result = judge.judge_board(board)
        assert result.score >= 0  # Should not crash

    def test_board_dimensions(self):
        judge = Judge()
        result = judge.judge_board(_board())
        dim_names = [d.name for d in result.dimensions]
        assert "cross_agent_consistency" in dim_names
        assert "agent_coverage" in dim_names
        assert "hard_guards" in dim_names
        assert "individual_quality" in dim_names


# ------------------------------------------------------------------ Grade mapping


class TestGradeMapping:
    def test_grade_a(self):
        assert Judge._score_to_grade(0.95) == "A"

    def test_grade_b(self):
        assert Judge._score_to_grade(0.85) == "B"

    def test_grade_c(self):
        assert Judge._score_to_grade(0.65) == "C"

    def test_grade_d(self):
        assert Judge._score_to_grade(0.45) == "D"

    def test_grade_f(self):
        assert Judge._score_to_grade(0.2) == "F"

    def test_grade_boundary(self):
        assert Judge._score_to_grade(0.9) == "A"
        assert Judge._score_to_grade(0.8) == "B"
        assert Judge._score_to_grade(0.6) == "C"
        assert Judge._score_to_grade(0.4) == "D"
