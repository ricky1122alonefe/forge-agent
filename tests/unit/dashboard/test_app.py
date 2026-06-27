"""Tests for the dashboard FastAPI application."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge_agent.dashboard.app import create_app


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a project root with a sample MANIFEST.json."""
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
    return tmp_path


@pytest.fixture
def app(project_root: Path):
    """Create a test FastAPI application."""
    return create_app(project_root=project_root, host="127.0.0.1", port=8765)


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_root_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "forge-agent Dashboard" in response.text

    def test_root_contains_tailwind(self, client):
        response = client.get("/")
        assert "tailwindcss.com" in response.text

    def test_root_contains_htmx(self, client):
        response = client.get("/")
        assert "htmx.org" in response.text

    def test_root_shows_agent_list(self, client):
        response = client.get("/")
        assert "stock.monitor" in response.text

    def test_root_shows_stats(self, client):
        response = client.get("/")
        assert "Total Agents" in response.text


class TestAgentsEndpoint:
    """Tests for the /api/agents endpoint."""

    def test_agents_returns_data(self, client):
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "stock.monitor" in data["agents"]

    def test_agents_empty_when_no_manifest(self, tmp_path: Path):
        app = create_app(project_root=tmp_path)
        client = TestClient(app)
        response = client.get("/api/agents")
        assert response.status_code == 200
        assert response.json() == {"agents": {}}


class TestAppCreation:
    """Tests for application creation."""

    def test_create_app_with_defaults(self, tmp_path: Path):
        app = create_app(project_root=tmp_path)
        assert app is not None
        assert app.title == "forge-agent Dashboard"

    def test_create_app_stores_project_root(self, tmp_path: Path):
        project_root = tmp_path / "custom"
        project_root.mkdir()
        app = create_app(project_root=project_root)
        assert app.state.project_root == project_root

    def test_create_app_stores_host_port(self, tmp_path: Path):
        app = create_app(project_root=tmp_path, host="0.0.0.0", port=9000)
        assert app.state.host == "0.0.0.0"
        assert app.state.port == 9000
