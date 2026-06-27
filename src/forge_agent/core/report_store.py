"""SQLiteReportStore — persistent storage for AgentReport history.

Schema:
    agent_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        name TEXT NOT NULL,
        domain TEXT NOT NULL,
        verdict TEXT NOT NULL,
        confidence REAL NOT NULL,
        risk REAL NOT NULL,
        weight REAL NOT NULL,
        evidence TEXT,  -- JSON array
        warnings TEXT,  -- JSON array
        recommended_action TEXT NOT NULL,
        metrics TEXT,   -- JSON object
        raw TEXT,       -- JSON object
        run_id TEXT,
        timestamp TEXT NOT NULL,
        version TEXT NOT NULL
    )
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict

log = logging.getLogger(__name__)

# Default DB location
_DEFAULT_DB_DIR = Path.home() / ".forge_agent"
_ENV_DB_PATH = "FORGE_AGENT_REPORTS_DB_PATH"


def _default_db_path() -> Path:
    env = os.environ.get(_ENV_DB_PATH)
    if env:
        return Path(env)
    return _DEFAULT_DB_DIR / "agent_reports.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteReportStore:
    """SQLite-backed persistent store for AgentReport history."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=10,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _ensure_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk REAL NOT NULL,
                weight REAL NOT NULL,
                evidence TEXT,
                warnings TEXT,
                recommended_action TEXT NOT NULL,
                metrics TEXT,
                raw TEXT,
                run_id TEXT,
                timestamp TEXT NOT NULL,
                version TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reports_agent_id
                ON agent_reports(agent_id);
            CREATE INDEX IF NOT EXISTS idx_reports_timestamp
                ON agent_reports(timestamp);
            CREATE INDEX IF NOT EXISTS idx_reports_verdict
                ON agent_reports(verdict);
            CREATE INDEX IF NOT EXISTS idx_reports_domain
                ON agent_reports(domain);
        """)
        self.conn.commit()

    def insert(self, report: AgentReport) -> AgentReport:
        """Insert a report and return it with the assigned id."""
        evidence_json = json.dumps(report.evidence, ensure_ascii=False) if report.evidence else None
        warnings_json = json.dumps(report.warnings, ensure_ascii=False) if report.warnings else None
        metrics_json = json.dumps(report.metrics, ensure_ascii=False) if report.metrics else None
        raw_json = json.dumps(report.raw, ensure_ascii=False) if report.raw else None

        timestamp = report.timestamp or _now_iso()

        cursor = self.conn.execute(
            """INSERT INTO agent_reports
               (agent_id, name, domain, verdict, confidence, risk, weight,
                evidence, warnings, recommended_action, metrics, raw,
                run_id, timestamp, version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report.agent_id,
                report.name,
                report.domain,
                report.verdict.value,
                float(report.confidence),
                float(report.risk),
                float(report.weight),
                evidence_json,
                warnings_json,
                report.recommended_action.value,
                metrics_json,
                raw_json,
                report.run_id,
                timestamp,
                report.version,
            ),
        )
        self.conn.commit()
        # Update the report with timestamp if it was empty
        if not report.timestamp:
            report.timestamp = timestamp
        return report

    def query(
        self,
        *,
        agent_id: str | None = None,
        domain: str | None = None,
        verdict: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[AgentReport]:
        """Query reports with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if domain is not None:
            conditions.append("domain = ?")
            params.append(domain)
        if verdict is not None:
            conditions.append("verdict = ?")
            params.append(verdict)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = f"""SELECT agent_id, name, domain, verdict, confidence, risk, weight,
                         evidence, warnings, recommended_action, metrics, raw,
                         run_id, timestamp, version
                  FROM agent_reports
                  {where}
                  ORDER BY timestamp DESC
                  LIMIT ?"""
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_report(row) for row in rows]

    def get_by_run_id(self, run_id: str) -> AgentReport | None:
        """Get a specific report by run_id."""
        sql = """SELECT agent_id, name, domain, verdict, confidence, risk, weight,
                        evidence, warnings, recommended_action, metrics, raw,
                        run_id, timestamp, version
                 FROM agent_reports
                 WHERE run_id = ?
                 LIMIT 1"""
        row = self.conn.execute(sql, (run_id,)).fetchone()
        return self._row_to_report(row) if row else None

    def summary(
        self,
        *,
        agent_id: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate statistics over matching reports."""
        conditions: list[str] = []
        params: list[Any] = []

        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if domain is not None:
            conditions.append("domain = ?")
            params.append(domain)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        # Overall stats
        sql = f"""SELECT
                      COUNT(*) as report_count,
                      COALESCE(AVG(confidence), 0.0) as avg_confidence,
                      COALESCE(AVG(risk), 0.0) as avg_risk,
                      COALESCE(AVG(weight), 0.0) as avg_weight
                  FROM agent_reports {where}"""
        row = self.conn.execute(sql, params).fetchone()
        result: dict[str, Any] = {
            "report_count": row[0],
            "avg_confidence": round(row[1], 3),
            "avg_risk": round(row[2], 3),
            "avg_weight": round(row[3], 3),
        }

        # Verdict distribution
        verdict_sql = f"""SELECT verdict, COUNT(*) as count
                          FROM agent_reports {where}
                          GROUP BY verdict
                          ORDER BY count DESC"""
        verdict_rows = self.conn.execute(verdict_sql, params).fetchall()
        result["by_verdict"] = {r[0]: r[1] for r in verdict_rows}

        # Domain distribution
        domain_sql = f"""SELECT domain, COUNT(*) as count
                         FROM agent_reports {where}
                         GROUP BY domain
                         ORDER BY count DESC"""
        domain_rows = self.conn.execute(domain_sql, params).fetchall()
        result["by_domain"] = {r[0]: r[1] for r in domain_rows}

        return result

    def reset(self) -> int:
        """Delete all records. Returns the number of deleted rows."""
        count = self.conn.execute("SELECT COUNT(*) FROM agent_reports").fetchone()[0]
        self.conn.execute("DELETE FROM agent_reports")
        self.conn.commit()
        return count

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_report(row: tuple) -> AgentReport:
        evidence: list[str] = []
        if row[7]:
            try:
                evidence = json.loads(row[7])
            except (json.JSONDecodeError, TypeError):
                pass

        warnings: list[str] = []
        if row[8]:
            try:
                warnings = json.loads(row[8])
            except (json.JSONDecodeError, TypeError):
                pass

        metrics: dict[str, float] = {}
        if row[10]:
            try:
                metrics = json.loads(row[10])
            except (json.JSONDecodeError, TypeError):
                pass

        raw: dict[str, Any] = {}
        if row[11]:
            try:
                raw = json.loads(row[11])
            except (json.JSONDecodeError, TypeError):
                pass

        return AgentReport(
            agent_id=row[0],
            name=row[1],
            domain=row[2],
            verdict=Verdict(row[3]),
            confidence=row[4],
            risk=row[5],
            weight=row[6],
            evidence=evidence,
            warnings=warnings,
            recommended_action=Action(row[9]),
            metrics=metrics,
            raw=raw,
            run_id=row[12],
            timestamp=row[13],
            version=row[14],
        )
