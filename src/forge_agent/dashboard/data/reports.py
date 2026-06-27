"""Dashboard data layer — Report history access."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge_agent.core.contracts import AgentReport
from forge_agent.core.report_store import SQLiteReportStore


@dataclass
class ReportSummary:
    """Lightweight report summary for dashboard display."""

    agent_id: str
    name: str
    domain: str
    verdict: str
    confidence: float
    risk: float
    timestamp: str
    run_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 3),
            "risk": round(self.risk, 3),
            "timestamp": self.timestamp,
            "run_id": self.run_id,
        }


@dataclass
class ReportDetail:
    """Full report detail with all fields."""

    agent_id: str
    name: str
    domain: str
    verdict: str
    confidence: float
    risk: float
    weight: float
    evidence: list[str]
    warnings: list[str]
    recommended_action: str
    metrics: dict[str, float]
    raw: dict[str, Any]
    run_id: str
    timestamp: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 3),
            "risk": round(self.risk, 3),
            "weight": round(self.weight, 3),
            "evidence": self.evidence,
            "warnings": self.warnings,
            "recommended_action": self.recommended_action,
            "metrics": self.metrics,
            "raw": self.raw,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "version": self.version,
        }


class ReportDataSource:
    """Dashboard-specific queries over AgentReport history."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._store = SQLiteReportStore(db_path)

    def list_reports(
        self,
        *,
        agent_id: str | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> list[ReportSummary]:
        """List recent reports as summaries."""
        reports = self._store.query(agent_id=agent_id, domain=domain, limit=limit)
        return [self._to_summary(r) for r in reports]

    def get_report(self, run_id: str) -> ReportDetail | None:
        """Get full report detail by run_id."""
        report = self._store.get_by_run_id(run_id)
        return self._to_detail(report) if report else None

    def get_reports_for_agent(self, agent_id: str, limit: int = 20) -> list[ReportSummary]:
        """Get recent reports for a specific agent."""
        reports = self._store.query(agent_id=agent_id, limit=limit)
        return [self._to_summary(r) for r in reports]

    def summary(
        self,
        *,
        agent_id: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregate statistics."""
        return self._store.summary(agent_id=agent_id, domain=domain)

    def close(self) -> None:
        """Close the underlying store."""
        self._store.close()

    @staticmethod
    def _to_summary(report: AgentReport) -> ReportSummary:
        return ReportSummary(
            agent_id=report.agent_id,
            name=report.name,
            domain=report.domain,
            verdict=report.verdict.value,
            confidence=float(report.confidence),
            risk=float(report.risk),
            timestamp=report.timestamp,
            run_id=report.run_id,
        )

    @staticmethod
    def _to_detail(report: AgentReport) -> ReportDetail:
        return ReportDetail(
            agent_id=report.agent_id,
            name=report.name,
            domain=report.domain,
            verdict=report.verdict.value,
            confidence=float(report.confidence),
            risk=float(report.risk),
            weight=float(report.weight),
            evidence=report.evidence,
            warnings=report.warnings,
            recommended_action=report.recommended_action.value,
            metrics=report.metrics,
            raw=report.raw,
            run_id=report.run_id,
            timestamp=report.timestamp,
            version=report.version,
        )
