"""Tests for the manifest data layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_agent.dashboard.data.manifest import AgentInfo, VersionInfo, load_manifest


@pytest.fixture
def project_with_manifest(tmp_path: Path) -> Path:
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
                        "llm_provider": "deepseek",
                        "llm_model": "deepseek-v4-flash",
                    },
                    {
                        "version": "v2",
                        "created_at": "2026-06-25T00:00:00+00:00",
                        "created_by": "cli",
                        "requirement": "monitor stock v2",
                        "validation_status": "passed",
                        "code_hash": "sha256:bbb",
                        "code_path": "stock.monitor/v2.py",
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


class TestLoadManifest:
    """Tests for load_manifest()."""

    def test_load_returns_agents(self, project_with_manifest: Path) -> None:
        agents = load_manifest(project_with_manifest)
        assert "stock.monitor" in agents

    def test_load_agent_info_fields(self, project_with_manifest: Path) -> None:
        agents = load_manifest(project_with_manifest)
        info = agents["stock.monitor"]
        assert info.agent_id == "stock.monitor"
        assert info.active_version == "v2"
        assert info.description == "Stock monitor"
        assert info.agent_type == "monitor"

    def test_load_versions(self, project_with_manifest: Path) -> None:
        agents = load_manifest(project_with_manifest)
        info = agents["stock.monitor"]
        assert len(info.versions) == 2
        assert info.versions[0].version == "v1"
        assert info.versions[1].version == "v2"

    def test_version_fields(self, project_with_manifest: Path) -> None:
        agents = load_manifest(project_with_manifest)
        v1 = agents["stock.monitor"].versions[0]
        assert v1.validation_status == "passed"
        assert v1.llm_provider == "deepseek"
        assert v1.llm_model == "deepseek-v4-flash"

    def test_load_empty_when_no_manifest(self, tmp_path: Path) -> None:
        agents = load_manifest(tmp_path)
        assert agents == {}

    def test_load_empty_when_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "generated_agents").mkdir()
        (tmp_path / "generated_agents" / "MANIFEST.json").write_text(
            "not valid json{{{", encoding="utf-8"
        )
        agents = load_manifest(tmp_path)
        assert agents == {}


class TestAgentInfo:
    """Tests for AgentInfo dataclass."""

    def test_to_dict(self) -> None:
        info = AgentInfo(
            agent_id="test.agent",
            created_at="2026-06-20T00:00:00+00:00",
            active_version="v1",
            versions=[
                VersionInfo(
                    version="v1",
                    created_at="2026-06-20T00:00:00+00:00",
                    created_by="cli",
                    requirement="test",
                    validation_status="passed",
                    code_hash="sha256:aaa",
                    code_path="test.agent/v1.py",
                ),
            ],
            description="Test agent",
            agent_type="general",
        )
        d = info.to_dict()
        assert d["agent_id"] == "test.agent"
        assert d["active_version"] == "v1"
        assert len(d["versions"]) == 1

    def test_version_count(self) -> None:
        info = AgentInfo(
            agent_id="test",
            created_at="",
            active_version="v1",
            versions=[
                VersionInfo(version="v1", created_at="", created_by="", requirement="", validation_status="", code_hash="", code_path=""),
                VersionInfo(version="v2", created_at="", created_by="", requirement="", validation_status="", code_hash="", code_path=""),
            ],
        )
        assert info.version_count == 2

    def test_active_version_info(self) -> None:
        v1 = VersionInfo(version="v1", created_at="", created_by="", requirement="", validation_status="passed", code_hash="", code_path="")
        v2 = VersionInfo(version="v2", created_at="", created_by="", requirement="", validation_status="failed", code_hash="", code_path="")
        info = AgentInfo(agent_id="test", created_at="", active_version="v2", versions=[v1, v2])
        active = info.active_version_info
        assert active is not None
        assert active.version == "v2"
        assert active.validation_status == "failed"

    def test_active_version_info_none(self) -> None:
        info = AgentInfo(agent_id="test", created_at="", active_version="v99", versions=[])
        assert info.active_version_info is None
