"""Smoke tests for the dashboard module (S2 safety net).

S2 will merge dashboard/ into web/observability/. These tests verify the
core entry points survive the merge: app creation, auth config, and data
layer imports.

Note: dashboard has a pre-existing Pydantic/Python 3.9 ForwardRef issue
in route type annotations. create_app() is tested defensively — if the
import environment is broken, the test documents it rather than hiding.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.dashboard.auth import AuthConfig


class TestAuthConfig:
    def test_disabled_by_default(self) -> None:
        config = AuthConfig()
        assert config.enabled is False

    def test_enable_with_api_key(self) -> None:
        config = AuthConfig(enabled=True, api_key="secret-key")
        assert config.enabled is True
        assert config.api_key == "secret-key"

    def test_validate_key(self) -> None:
        config = AuthConfig(enabled=True, api_key="secret")
        assert config.validate_key("secret") is True
        assert config.validate_key("wrong") is False
        assert config.validate_key(None) is False

    def test_disabled_allows_all(self) -> None:
        config = AuthConfig()
        assert config.validate_key(None) is True
        assert config.validate_key("anything") is True


class TestAppCreation:
    """create_app() must return a FastAPI instance with routes mounted.

    If this fails, the dashboard cannot start — critical for S2 merge.
    """

    @pytest.fixture
    def project_root(self, tmp_path) -> Path:
        (tmp_path / "agents").mkdir()
        (tmp_path / "pipelines").mkdir()
        (tmp_path / "state").mkdir()
        return tmp_path

    def test_create_app_returns_fastapi(self, project_root: Path) -> None:
        from fastapi import FastAPI

        from forge_agent.dashboard.app import create_app

        app = create_app(project_root=project_root)
        assert isinstance(app, FastAPI)
        assert app.title == "forge-agent Dashboard"

    def test_app_has_routes(self, project_root: Path) -> None:
        from forge_agent.dashboard.app import create_app

        app = create_app(project_root=project_root)
        route_paths = {r.path for r in app.routes if hasattr(r, "path")}
        # Dashboard should mount pages + api + ws routes
        assert len(route_paths) > 0

    def test_app_state_stores_project_root(self, project_root: Path) -> None:
        from forge_agent.dashboard.app import create_app

        app = create_app(project_root=project_root)
        assert app.state.project_root == project_root

    def test_app_with_auth(self, project_root: Path) -> None:
        from forge_agent.dashboard.app import create_app

        auth = AuthConfig(enabled=True, api_key="test-key")
        app = create_app(project_root=project_root, auth_config=auth)
        assert app is not None


class TestDataLayerImports:
    """Verify the dashboard data layer modules are importable.

    These will move to web/observability/ in S2 — imports must survive.
    """

    def test_import_manifest_data(self) -> None:
        from forge_agent.dashboard import data

        assert hasattr(data, "__path__")

    def test_import_routes(self) -> None:
        from forge_agent.dashboard.routes import api, pages, ws

        assert hasattr(api, "router")
        assert hasattr(pages, "router")
        assert hasattr(ws, "router")
