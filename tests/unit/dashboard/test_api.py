"""Tests for REST API endpoints (D1.3 + D2.x)."""

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
                "active_version": "v2",
                "versions": [
                    {
                        "version": "v1",
                        "created_at": "2026-06-20T00:00:00+00:00",
                        "created_by": "cli",
                        "requirement": "monitor stock",
                        "validation_status": "passed",
                        "code_hash": "sha256:aaa",
                        "code_path": "stock.monitor/v1.py",
                    },
                    {
                        "version": "v2",
                        "created_at": "2026-06-25T00:00:00+00:00",
                        "created_by": "cli",
                        "requirement": "monitor stock v2",
                        "validation_status": "passed",
                        "code_hash": "sha256:bbb",
                        "code_path": "stock.monitor/v2.py",
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


class TestListAgentsAPI:
    """Tests for GET /api/agents."""

    def test_list_agents(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/agents")
        assert r.status_code == 200
        data = r.json()
        assert "stock.monitor" in data["agents"]
        agent = data["agents"]["stock.monitor"]
        assert agent["active_version"] == "v2"
        assert len(agent["versions"]) == 2

    def test_list_agents_empty(self, tmp_path: Path) -> None:
        client = TestClient(create_app(project_root=tmp_path))
        r = client.get("/api/agents")
        assert r.status_code == 200
        assert r.json() == {"agents": {}}


class TestGetAgentAPI:
    """Tests for GET /api/agents/{agent_id}."""

    def test_get_agent(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/agents/stock.monitor")
        assert r.status_code == 200
        data = r.json()
        assert data["active_version"] == "v2"
        assert data["agent_id"] == "stock.monitor"
        assert data["agent_type"] == "monitor"

    def test_get_agent_not_found(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/agents/nonexistent")
        assert r.status_code == 404

    def test_get_agent_has_versions(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/agents/stock.monitor")
        data = r.json()
        assert len(data["versions"]) == 2


class TestTracesAPI:
    """Tests for GET /api/traces."""

    def test_list_traces_empty(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/traces")
        assert r.status_code == 200
        assert r.json() == {"traces": []}

    def test_get_trace_not_found(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/traces/nonexistent")
        assert r.status_code == 404


class TestMetricsAPI:
    """Tests for GET /api/metrics."""

    def test_get_metrics(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data


class TestReportsAPI:
    """Tests for GET /api/reports."""

    def test_list_reports_empty(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/reports")
        assert r.status_code == 200
        assert r.json() == {"reports": []}

    def test_get_report_not_found(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/reports/nonexistent")
        assert r.status_code == 404

    def test_get_report_summary(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/api/reports/summary")
        assert r.status_code == 200
        data = r.json()
        assert "report_count" in data
        assert data["report_count"] == 0
