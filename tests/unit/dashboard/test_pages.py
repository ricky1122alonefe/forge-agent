"""Tests for page routes (D1.2)."""

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
        """When no MANIFEST.json, show empty state."""
        client = TestClient(create_app(project_root=tmp_path))
        r = client.get("/")
        assert r.status_code == 200
        assert "No agents generated yet" in r.text

    def test_index_shows_stats(self, client_with_manifest: TestClient) -> None:
        r = client_with_manifest.get("/")
        assert r.status_code == 200
        assert "Total Agents" in r.text
        assert "Total Versions" in r.text
