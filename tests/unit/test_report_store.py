"""Tests for SQLiteReportStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.report_store import SQLiteReportStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteReportStore:
    """Create a temporary SQLiteReportStore."""
    return SQLiteReportStore(db_path=tmp_path / "test_reports.db")


@pytest.fixture
def sample_report() -> AgentReport:
    """Create a sample AgentReport."""
    return AgentReport(
        agent_id="stock.monitor",
        name="Stock Monitor",
        domain="stock",
        verdict=Verdict.LEAN_POSITIVE,
        confidence=0.85,
        risk=0.15,
        weight=1.0,
        evidence=["Price above MA20", "Volume increasing"],
        warnings=["Market volatile"],
        recommended_action=Action.EXECUTE,
        metrics={"price_change": 2.5},
        raw={"llm_response": "buy signal"},
        run_id="run_001",
        timestamp="2026-06-27T10:00:00+00:00",
        version="v1",
    )


class TestSQLiteReportStore:
    """Tests for SQLiteReportStore."""

    def test_insert_and_query(self, store: SQLiteReportStore, sample_report: AgentReport) -> None:
        store.insert(sample_report)
        results = store.query()
        assert len(results) == 1
        assert results[0].agent_id == "stock.monitor"
        assert results[0].verdict == Verdict.LEAN_POSITIVE

    def test_insert_multiple(self, store: SQLiteReportStore) -> None:
        for i in range(5):
            report = AgentReport(
                agent_id=f"agent_{i}",
                name=f"Agent {i}",
                domain="test",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id=f"run_{i}",
                timestamp=f"2026-06-27T{10 + i}:00:00+00:00",
            )
            store.insert(report)
        results = store.query()
        assert len(results) == 5

    def test_query_by_agent_id(self, store: SQLiteReportStore) -> None:
        store.insert(
            AgentReport(
                agent_id="stock.monitor",
                name="Stock",
                domain="stock",
                verdict=Verdict.LEAN_POSITIVE,
                confidence=0.8,
                risk=0.2,
                run_id="run_1",
                timestamp="2026-06-27T10:00:00+00:00",
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
                run_id="run_2",
                timestamp="2026-06-27T11:00:00+00:00",
            )
        )
        results = store.query(agent_id="stock.monitor")
        assert len(results) == 1
        assert results[0].agent_id == "stock.monitor"

    def test_query_by_domain(self, store: SQLiteReportStore) -> None:
        store.insert(
            AgentReport(
                agent_id="a1",
                name="A1",
                domain="stock",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id="r1",
                timestamp="2026-06-27T10:00:00+00:00",
            )
        )
        store.insert(
            AgentReport(
                agent_id="a2",
                name="A2",
                domain="football",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id="r2",
                timestamp="2026-06-27T11:00:00+00:00",
            )
        )
        results = store.query(domain="stock")
        assert len(results) == 1
        assert results[0].domain == "stock"

    def test_query_by_verdict(self, store: SQLiteReportStore) -> None:
        store.insert(
            AgentReport(
                agent_id="a1",
                name="A1",
                domain="test",
                verdict=Verdict.LEAN_POSITIVE,
                confidence=0.8,
                risk=0.2,
                run_id="r1",
                timestamp="2026-06-27T10:00:00+00:00",
            )
        )
        store.insert(
            AgentReport(
                agent_id="a2",
                name="A2",
                domain="test",
                verdict=Verdict.LEAN_NEGATIVE,
                confidence=0.3,
                risk=0.7,
                run_id="r2",
                timestamp="2026-06-27T11:00:00+00:00",
            )
        )
        results = store.query(verdict="lean_positive")
        assert len(results) == 1
        assert results[0].verdict == Verdict.LEAN_POSITIVE

    def test_query_with_limit(self, store: SQLiteReportStore) -> None:
        for i in range(10):
            store.insert(
                AgentReport(
                    agent_id=f"agent_{i}",
                    name=f"Agent {i}",
                    domain="test",
                    verdict=Verdict.NEUTRAL,
                    confidence=0.5,
                    risk=0.5,
                    run_id=f"run_{i}",
                    timestamp=f"2026-06-27T{10 + i}:00:00+00:00",
                )
            )
        results = store.query(limit=3)
        assert len(results) == 3

    def test_get_by_run_id(self, store: SQLiteReportStore, sample_report: AgentReport) -> None:
        store.insert(sample_report)
        result = store.get_by_run_id("run_001")
        assert result is not None
        assert result.run_id == "run_001"
        assert result.agent_id == "stock.monitor"

    def test_get_by_run_id_not_found(self, store: SQLiteReportStore) -> None:
        result = store.get_by_run_id("nonexistent")
        assert result is None

    def test_summary(self, store: SQLiteReportStore) -> None:
        store.insert(
            AgentReport(
                agent_id="a1",
                name="A1",
                domain="stock",
                verdict=Verdict.LEAN_POSITIVE,
                confidence=0.8,
                risk=0.2,
                weight=1.0,
                run_id="r1",
                timestamp="2026-06-27T10:00:00+00:00",
            )
        )
        store.insert(
            AgentReport(
                agent_id="a2",
                name="A2",
                domain="stock",
                verdict=Verdict.LEAN_NEGATIVE,
                confidence=0.4,
                risk=0.6,
                weight=2.0,
                run_id="r2",
                timestamp="2026-06-27T11:00:00+00:00",
            )
        )
        summary = store.summary()
        assert summary["report_count"] == 2
        assert summary["avg_confidence"] == 0.6
        assert summary["avg_risk"] == 0.4
        assert summary["avg_weight"] == 1.5
        assert "lean_positive" in summary["by_verdict"]
        assert "stock" in summary["by_domain"]

    def test_summary_with_filter(self, store: SQLiteReportStore) -> None:
        store.insert(
            AgentReport(
                agent_id="a1",
                name="A1",
                domain="stock",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id="r1",
                timestamp="2026-06-27T10:00:00+00:00",
            )
        )
        store.insert(
            AgentReport(
                agent_id="a2",
                name="A2",
                domain="football",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id="r2",
                timestamp="2026-06-27T11:00:00+00:00",
            )
        )
        summary = store.summary(domain="stock")
        assert summary["report_count"] == 1

    def test_reset(self, store: SQLiteReportStore) -> None:
        store.insert(
            AgentReport(
                agent_id="a1",
                name="A1",
                domain="test",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id="r1",
                timestamp="2026-06-27T10:00:00+00:00",
            )
        )
        count = store.reset()
        assert count == 1
        results = store.query()
        assert len(results) == 0

    def test_evidence_and_warnings_preserved(
        self, store: SQLiteReportStore, sample_report: AgentReport
    ) -> None:
        store.insert(sample_report)
        result = store.get_by_run_id("run_001")
        assert result is not None
        assert result.evidence == ["Price above MA20", "Volume increasing"]
        assert result.warnings == ["Market volatile"]

    def test_metrics_and_raw_preserved(
        self, store: SQLiteReportStore, sample_report: AgentReport
    ) -> None:
        store.insert(sample_report)
        result = store.get_by_run_id("run_001")
        assert result is not None
        assert result.metrics == {"price_change": 2.5}
        assert result.raw == {"llm_response": "buy signal"}

    def test_auto_timestamp(self, store: SQLiteReportStore) -> None:
        report = AgentReport(
            agent_id="a1",
            name="A1",
            domain="test",
            verdict=Verdict.NEUTRAL,
            confidence=0.5,
            risk=0.5,
            run_id="r1",
        )
        store.insert(report)
        result = store.get_by_run_id("r1")
        assert result is not None
        assert result.timestamp != ""

    def test_close_and_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        store1 = SQLiteReportStore(db_path=db_path)
        store1.insert(
            AgentReport(
                agent_id="a1",
                name="A1",
                domain="test",
                verdict=Verdict.NEUTRAL,
                confidence=0.5,
                risk=0.5,
                run_id="r1",
                timestamp="2026-06-27T10:00:00+00:00",
            )
        )
        store1.close()

        store2 = SQLiteReportStore(db_path=db_path)
        results = store2.query()
        assert len(results) == 1
        store2.close()
