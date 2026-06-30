"""Tests for `forge-agent new` and `forge-agent list-projects`."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge_agent.cli import main


@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    root = tmp_path / "forge-test"
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _run(*argv: str) -> int:
    """Helper to invoke the CLI and swallow prints."""
    return main(list(argv))


class TestCmdNew:
    def test_creates_project_under_tenant(self, temp_root: Path) -> None:
        rc = _run("--project", str(temp_root), "new", "demo", "--tenant", "acme")
        assert rc == 0

        project_path = temp_root / "tenants" / "acme" / "projects" / "demo"
        assert project_path.exists()
        assert (project_path / "agents").is_dir()
        assert (project_path / "pipelines").is_dir()
        assert (project_path / "state").is_dir()
        assert (project_path / "logs").is_dir()

    def test_same_project_name_different_tenants_isolated(self, temp_root: Path) -> None:
        _run("--project", str(temp_root), "new", "demo", "--tenant", "acme")
        _run("--project", str(temp_root), "new", "demo", "--tenant", "bob")

        acme_path = temp_root / "tenants" / "acme" / "projects" / "demo"
        bob_path = temp_root / "tenants" / "bob" / "projects" / "demo"

        assert acme_path.exists()
        assert bob_path.exists()
        assert acme_path != bob_path

    def test_duplicate_project_fails(self, temp_root: Path) -> None:
        _run("--project", str(temp_root), "new", "demo", "--tenant", "acme")
        rc = _run("--project", str(temp_root), "new", "demo", "--tenant", "acme")

        assert rc == 1


class TestCmdListProjects:
    def test_lists_projects_for_tenant(self, temp_root: Path) -> None:
        _run("--project", str(temp_root), "new", "alpha", "--tenant", "acme")
        _run("--project", str(temp_root), "new", "beta", "--tenant", "acme")

        rc = _run("--project", str(temp_root), "list-projects", "--tenant", "acme")

        assert rc == 0

    def test_empty_tenant_returns_zero(self, temp_root: Path) -> None:
        rc = _run("--project", str(temp_root), "list-projects", "--tenant", "empty")

        assert rc == 0
