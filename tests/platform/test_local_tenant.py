"""Tests for LocalTenant."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge_agent.exceptions import ProjectAlreadyExistsError, ProjectNotFoundError
from forge_agent.platform import LocalTenant


@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    return tmp_path / "forge-agent"


@pytest.fixture
def tenant(temp_root: Path) -> LocalTenant:
    return LocalTenant("acme", root_dir=temp_root)


class TestLocalTenant:
    def test_create_project_makes_directory_tree(self, tenant: LocalTenant) -> None:
        project_root = tenant.create_project("trend_demo")

        assert project_root.exists()
        assert (project_root / "agents").is_dir()
        assert (project_root / "pipelines").is_dir()
        assert (project_root / "tools").is_dir()
        assert (project_root / "configs").is_dir()
        assert (project_root / "state").is_dir()
        assert (project_root / "logs").is_dir()

    def test_create_project_raises_if_exists(self, tenant: LocalTenant) -> None:
        tenant.create_project("trend_demo")

        with pytest.raises(ProjectAlreadyExistsError):
            tenant.create_project("trend_demo")

    def test_project_exists(self, tenant: LocalTenant) -> None:
        assert tenant.project_exists("trend_demo") is False
        tenant.create_project("trend_demo")
        assert tenant.project_exists("trend_demo") is True

    def test_get_project_path(self, tenant: LocalTenant) -> None:
        tenant.create_project("trend_demo")

        path = tenant.get_project_path("trend_demo")

        assert path.name == "trend_demo"
        assert path.is_dir()

    def test_get_project_path_missing_raises(self, tenant: LocalTenant) -> None:
        with pytest.raises(ProjectNotFoundError):
            tenant.get_project_path("missing")

    def test_list_projects(self, tenant: LocalTenant) -> None:
        tenant.create_project("alpha")
        tenant.create_project("beta")

        assert tenant.list_projects() == ["alpha", "beta"]

    def test_list_projects_empty(self, tenant: LocalTenant) -> None:
        assert tenant.list_projects() == []

    def test_delete_project(self, tenant: LocalTenant) -> None:
        tenant.create_project("trend_demo")
        tenant.delete_project("trend_demo")

        assert tenant.project_exists("trend_demo") is False

    def test_delete_missing_project_raises(self, tenant: LocalTenant) -> None:
        with pytest.raises(ProjectNotFoundError):
            tenant.delete_project("missing")

    def test_get_state_path(self, tenant: LocalTenant) -> None:
        tenant.create_project("trend_demo")
        state_path = tenant.get_state_path("trend_demo")

        assert state_path.name == "state"
        assert state_path.is_dir()

    def test_get_logs_path(self, tenant: LocalTenant) -> None:
        tenant.create_project("trend_demo")
        logs_path = tenant.get_logs_path("trend_demo")

        assert logs_path.name == "logs"
        assert logs_path.is_dir()

    def test_get_shared_path(self, tenant: LocalTenant) -> None:
        shared_path = tenant.get_shared_path()

        assert shared_path.name == "shared"
        assert shared_path.is_dir()

    def test_ensure_project_creates_when_missing(self, tenant: LocalTenant) -> None:
        path = tenant.ensure_project("trend_demo")

        assert path.exists()
        assert tenant.project_exists("trend_demo")

    def test_ensure_project_returns_existing(self, tenant: LocalTenant) -> None:
        created = tenant.create_project("trend_demo")
        ensured = tenant.ensure_project("trend_demo")

        assert created == ensured

    def test_tenant_isolation(self, temp_root: Path) -> None:
        tenant_a = LocalTenant("acme", root_dir=temp_root)
        tenant_b = LocalTenant("bob", root_dir=temp_root)

        tenant_a.create_project("trend_demo")
        tenant_b.create_project("trend_demo")

        assert tenant_a.list_projects() == ["trend_demo"]
        assert tenant_b.list_projects() == ["trend_demo"]
        assert tenant_a.get_project_path("trend_demo") != tenant_b.get_project_path("trend_demo")

    def teardown_method(self) -> None:
        # Best-effort cleanup of the default test root if it was created.
        default = LocalTenant.DEFAULT_ROOT
        if default.exists():
            shutil.rmtree(default, ignore_errors=True)
