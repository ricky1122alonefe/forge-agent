"""Tests for page routes (D1.2 + D2.1-D2.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge_agent.dashboard.app import create_app


@pytest.fixture
def client_with_manifest(tmp_path: Path) -> TestClient:
    """A project with a sample MANIFEST.json."""
    (tmp_path / "generated_agents").mkdir()
    manifest = {
        "version": 2,
        "project": "test",
        "updated_at": "2026-06-27T00:00:00+00:00",
        "agents": {
            "stock.monitor": {
                "agent_id": "stock.monitor",
                "created_at": "2026-06-20T00:00:00+00:00",
                "active_version": "v1",
                "versions": [
                    {
                        "version": "v1",
                        "created_at": "2026-06-20T00:00:00+00:00",
                        "created_by": "cli",
                        "requirement": "monitor stock",
                        "validation_status": "passed",
                        "code_hash": "sha256:aaa",
                        "code_path": "stock.monitor/v1.py",
                        "llm_provider": "deepseek",
                        "llm_model": "deepseek-v4-flash",
                    },
                ],
                "description": "Stock monitor",
                "agent_type": "monitor",
            },
        },
        "archive": [],
    }
    (tmp_path / "generated_agents" / "MANIFEST.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return TestClient(create_app(project_root=tmp_path))


class TestIndexPage:
    """Tests for the index page (GET /)."""

    def test_index_renders(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "forge-agent Dashboard" in r.text

    def test_index_lists_agents(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "stock.monitor" in r.text

    def test_index_shows_agent_type(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "monitor" in r.text

    def test_index_shows_validation_status(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "passed" in r.text

    def test_index_shows_llm_model(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "deepseek-v4-flash" in r.text

    def test_index_empty_state(self, tmp_path: Path) -> None:
        client = TestClient(create_app(project_root=tmp_path))
        r = client.get("/")
        assert r.status_code == 200
        assert "No agents generated yet" in r.text

    def test_index_shows_stats(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "Total Agents" in r.text
        assert "Total Versions" in r.text


class TestAgentDetailPage:
    """Tests for the agent detail page (GET /agents/{id})."""

    def test_detail_renders(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/agents/stock.monitor")
        assert r.status_code == 200
        assert "stock.monitor" in r.text

    def test_detail_shows_versions(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/agents/stock.monitor")
        assert r.status_code == 200
        assert "v1" in r.text
        assert "active" in r.text

    def test_detail_shows_description(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/agents/stock.monitor")
        assert r.status_code == 200
        assert "Stock monitor" in r.text

    def test_detail_shows_type(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/agents/stock.monitor")
        assert r.status_code == 200
        assert "monitor" in r.text

    def test_detail_not_found(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/agents/nonexistent")
        assert r.status_code == 404

    def test_detail_has_breadcrumb(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/agents/stock.monitor")
        assert r.status_code == 200
        assert "Agents" in r.text


class TestTracesPage:
    """Tests for the traces page (GET /traces)."""

    def test_traces_renders(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/traces")
        assert r.status_code == 200
        assert "Traces" in r.text

    def test_traces_empty_state(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/traces")
        assert r.status_code == 200
        assert "No traces recorded yet" in r.text

    def test_traces_has_ws_controls(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/traces")
        assert r.status_code == 200
        assert "Connect Logs" in r.text
        assert "Live Log Stream" in r.text


class TestTraceDetailPage:
    """Tests for the trace detail page (GET /traces/{trace_id})."""

    def test_trace_detail_not_found(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/traces/nonexistent")
        assert r.status_code == 404


class TestMetricsPage:
    """Tests for the metrics page (GET /metrics)."""

    def test_metrics_renders(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/metrics")
        assert r.status_code == 200
        assert "Metrics" in r.text

    def test_metrics_has_sections(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/metrics")
        assert r.status_code == 200
        assert "Counters" in r.text
        assert "Gauges" in r.text
        assert "Histograms" in r.text


class TestReportsPage:
    """Tests for the reports page (GET /reports)."""

    def test_reports_renders(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/reports")
        assert r.status_code == 200
        assert "Reports" in r.text

    def test_reports_empty_state(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/reports")
        assert r.status_code == 200
        assert "No reports recorded yet" in r.text

    def test_reports_has_summary(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/reports")
        assert r.status_code == 200
        assert "Total Reports" in r.text
        assert "Avg Confidence" in r.text
