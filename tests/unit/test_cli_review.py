"""Tests for `forge-agent review` CLI command."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from forge_agent.cli import cmd_review
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.report_store import SQLiteReportStore


@pytest.fixture
def report_db(tmp_path: Path) -> Path:
    store = SQLiteReportStore(db_path=tmp_path / "reports.db")
    store.insert(
        AgentReport(
            agent_id="football.home_expert",
            name="Home Expert",
            domain="football",
            verdict=Verdict.LEAN_POSITIVE,
            confidence=0.8,
            risk=0.2,
            weight=1.0,
            recommended_action=Action.EXECUTE,
            evidence=["home win predicted"],
            run_id="match-cli-1",
        )
    )
    return tmp_path / "reports.db"


def test_review_command_records_outcome(report_db: Path):
    args = argparse.Namespace(
        agent_id="football.home_expert",
        run_id="match-cli-1",
        winner="home",
        home_score=2.0,
        away_score=0.0,
        note=["clean sheet"],
        evolve=False,
        report_db=report_db,
    )
    rc = cmd_review.run(args)
    assert rc == 0


def test_review_command_evolve_triggered(report_db: Path):
    store = SQLiteReportStore(db_path=report_db)
    store.insert(
        AgentReport(
            agent_id="football.bad_expert",
            name="Bad Expert",
            domain="football",
            verdict=Verdict.LEAN_POSITIVE,
            confidence=0.95,
            risk=0.05,
            weight=1.0,
            recommended_action=Action.EXECUTE,
            evidence=["sure home win"],
            run_id="match-cli-2",
        )
    )
    args = argparse.Namespace(
        agent_id="football.bad_expert",
        run_id="match-cli-2",
        winner="away",
        home_score=0.0,
        away_score=3.0,
        note=[],
        evolve=True,
        report_db=report_db,
    )
    rc = cmd_review.run(args)
    assert rc == 0
