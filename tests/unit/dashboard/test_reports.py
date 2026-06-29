"""Tests for report data access layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.report_store import SQLiteReportStore
from forge_agent.dashboard.data.reports import ReportDataSource, ReportDetail, ReportSummary


@pytest.fixture
def report_source(tmp_path: Path) -> ReportDataSource:
    """Create a ReportDataSource with temp DB."""
    return ReportDataSource(db_path=tmp_path / "test_reports.db")


@pytest.fixture
def populated_source(tmp_path: Path) -> ReportDataSource:
    """Create a ReportDataSource with sample data."""
    source = ReportDataSource(db_path=tmp_path / "test_reports.db")
    store = SQLiteReportStore(db_path=tmp_path / "test_reports.db")
    store.insert(
        AgentReport(
            agent_id="stock.monitor",
            name="Stock Monitor",
            domain="stock",
            verdict=Verdict.LEAN_POSITIVE,
            confidence=0.85,
            risk=0.15,
            weight=1.0,
            evidence=["Price up"],
            warnings=[],
            recommended_action=Action.EXECUTE,
            metrics={"change": 2.5},
            raw={},
            run_id="run_001",
            timestamp="2026-06-27T10:00:00+00:00",
            version="v1",
        )
    )
    store.insert(
        AgentReport(
            agent_id="football.predictor",
            name="Football",
            domain="football",
            verdict=Verdict.LEAN_NEUTRAL,
            confidence=0.6,
            risk=0.3,
            weight=1.0,
            evidence=[],
            warnings=[],
            recommended_action=Action.WATCH,
            metrics={},
            raw={},
            run_id="run_002",
            timestamp="2026-06-27T11:00:00+00:00",
            version="v1",
        )
    )
    store.close()
    return source


class TestReportDataSource:
    """Tests for ReportDataSource."""

    def test_list_reports_empty(self, report_source: ReportDataSource) -> None:
        reports = report_source.list_reports()
        assert reports == []

    def test_list_reports_with_data(self, populated_source: ReportDataSource) -> None:
        reports = populated_source.list_reports()
        assert len(reports) == 2
        assert all(isinstance(r, ReportSummary) for r in reports)

    def test_list_reports_by_agent(self, populated_source: ReportDataSource) -> None:
        reports = populated_source.list_reports(agent_id="stock.monitor")
        assert len(reports) == 1
        assert reports[0].agent_id == "stock.monitor"

    def test_list_reports_by_domain(self, populated_source: ReportDataSource) -> None:
        reports = populated_source.list_reports(domain="football")
        assert len(reports) == 1
        assert reports[0].domain == "football"

    def test_get_report(self, populated_source: ReportDataSource) -> None:
        detail = populated_source.get_report("run_001")
        assert detail is not None
        assert isinstance(detail, ReportDetail)
        assert detail.run_id == "run_001"
        assert detail.agent_id == "stock.monitor"
        assert detail.evidence == ["Price up"]

    def test_get_report_not_found(self, report_source: ReportDataSource) -> None:
        detail = report_source.get_report("nonexistent")
        assert detail is None

    def test_get_reports_for_agent(self, populated_source: ReportDataSource) -> None:
        reports = populated_source.get_reports_for_agent("stock.monitor")
        assert len(reports) == 1
        assert reports[0].agent_id == "stock.monitor"

    def test_summary(self, populated_source: ReportDataSource) -> None:
        summary = populated_source.summary()
        assert summary["report_count"] == 2
        assert "by_verdict" in summary
        assert "by_domain" in summary

    def test_summary_with_filter(self, populated_source: ReportDataSource) -> None:
        summary = populated_source.summary(domain="stock")
        assert summary["report_count"] == 1


class TestReportSummary:
    """Tests for ReportSummary dataclass."""

    def test_to_dict(self) -> None:
        summary = ReportSummary(
            agent_id="test.agent",
            name="Test Agent",
            domain="test",
            verdict="lean_positive",
            confidence=0.85,
            risk=0.15,
            timestamp="2026-06-27T10:00:00+00:00",
            run_id="run_001",
        )
        d = summary.to_dict()
        assert d["agent_id"] == "test.agent"
        assert d["confidence"] == 0.85
        assert d["run_id"] == "run_001"


class TestReportDetail:
    """Tests for ReportDetail dataclass."""

    def test_to_dict(self) -> None:
        detail = ReportDetail(
            agent_id="test.agent",
            name="Test Agent",
            domain="test",
            verdict="lean_positive",
            confidence=0.85,
            risk=0.15,
            weight=1.0,
            evidence=["evidence 1"],
            warnings=["warning 1"],
            recommended_action="execute",
            metrics={"score": 0.9},
            raw={"data": "value"},
            run_id="run_001",
            timestamp="2026-06-27T10:00:00+00:00",
            version="v1",
        )
        d = detail.to_dict()
        assert d["agent_id"] == "test.agent"
        assert d["evidence"] == ["evidence 1"]
        assert d["metrics"] == {"score": 0.9}
        assert d["version"] == "v1"
