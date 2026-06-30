"""Tests for StateStore."""

from __future__ import annotations

from pathlib import Path

from forge_agent.project.state_store import RunRecord, StateStore, generate_run_id


class TestStateStore:
    def test_save_and_list(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        record = RunRecord(
            run_id="20250101_120000_demo",
            timestamp="2025-01-01T12:00:00+00:00",
            pipeline_id="demo",
            pipeline_name="Demo Pipeline",
            tenant_id="acme",
            project_id="demo",
            payload={},
            agent_reports=[],
            chief_summary=None,
            metadata={},
        )

        path = store.save(record)

        assert path.exists()
        assert (tmp_path / "state" / "latest.json").exists()
        assert store.list()[0].run_id == "20250101_120000_demo"

    def test_get_existing(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        record = RunRecord(
            run_id="20250101_120000_demo",
            timestamp="2025-01-01T12:00:00+00:00",
            pipeline_id="demo",
            pipeline_name="Demo Pipeline",
            tenant_id="acme",
            project_id="demo",
            payload={"key": "value"},
            agent_reports=[],
            chief_summary=None,
            metadata={},
        )
        store.save(record)

        fetched = store.get("20250101_120000_demo")

        assert fetched is not None
        assert fetched.payload == {"key": "value"}

    def test_get_missing_returns_none(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        assert store.get("missing") is None

    def test_latest(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path)
        record = RunRecord(
            run_id="20250101_120000_demo",
            timestamp="2025-01-01T12:00:00+00:00",
            pipeline_id="demo",
            pipeline_name="Demo Pipeline",
            tenant_id="acme",
            project_id="demo",
            payload={},
            agent_reports=[],
            chief_summary=None,
            metadata={},
        )
        store.save(record)

        latest = store.latest()
        assert latest is not None
        assert latest.run_id == "20250101_120000_demo"


class TestGenerateRunId:
    def test_contains_pipeline_and_timestamp(self) -> None:
        run_id = generate_run_id("trend")
        assert run_id.startswith("20")
        assert "trend" in run_id
