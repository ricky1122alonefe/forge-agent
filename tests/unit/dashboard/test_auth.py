"""Tests for dashboard authentication and authorization."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge_agent.dashboard.app import create_app
from forge_agent.dashboard.auth import (
    AuthConfig,
    get_auth_config,
    reset_auth_config,
    set_auth_config,
)


@pytest.fixture(autouse=True)
def clean_auth():
    """Reset auth config before and after each test."""
    reset_auth_config()
    yield
    reset_auth_config()


class TestAuthConfig:
    """Tests for AuthConfig."""

    def test_default_disabled(self) -> None:
        config = AuthConfig()
        assert config.enabled is False
        assert config.api_key is None
        assert config.header_name == "X-API-Key"

    def test_validate_key_disabled(self) -> None:
        config = AuthConfig(enabled=False)
        assert config.validate_key(None) is True
        assert config.validate_key("anything") is True

    def test_validate_key_no_api_key_set(self) -> None:
        config = AuthConfig(enabled=True, api_key=None)
        assert config.validate_key(None) is True

    def test_validate_key_correct(self) -> None:
        config = AuthConfig(enabled=True, api_key="secret123")
        assert config.validate_key("secret123") is True

    def test_validate_key_wrong(self) -> None:
        config = AuthConfig(enabled=True, api_key="secret123")
        assert config.validate_key("wrong") is False

    def test_validate_key_missing(self) -> None:
        config = AuthConfig(enabled=True, api_key="secret123")
        assert config.validate_key(None) is False

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FORGE_AGENT_AUTH_ENABLED", raising=False)
        monkeypatch.delenv("FORGE_AGENT_API_KEY", raising=False)
        monkeypatch.delenv("FORGE_AGENT_AUTH_HEADER", raising=False)
        config = AuthConfig.from_env()
        assert config.enabled is False
        assert config.api_key is None

    def test_from_env_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_AGENT_AUTH_ENABLED", "true")
        monkeypatch.setenv("FORGE_AGENT_API_KEY", "my-key")
        config = AuthConfig.from_env()
        assert config.enabled is True
        assert config.api_key == "my-key"


class TestAuthMiddleware:
    """Tests for AuthMiddleware integration."""

    def test_no_auth_allows_all(self, tmp_path: Path) -> None:
        app = create_app(project_root=tmp_path)
        client = TestClient(app)
        r = client.get("/api/agents")
        assert r.status_code == 200

    def test_auth_enabled_blocks_without_key(self, tmp_path: Path) -> None:
        auth = AuthConfig(enabled=True, api_key="secret123")
        app = create_app(project_root=tmp_path, auth_config=auth)
        client = TestClient(app)
        r = client.get("/api/agents")
        assert r.status_code == 401

    def test_auth_enabled_allows_with_key(self, tmp_path: Path) -> None:
        auth = AuthConfig(enabled=True, api_key="secret123")
        app = create_app(project_root=tmp_path, auth_config=auth)
        client = TestClient(app)
        r = client.get("/api/agents", headers={"X-API-Key": "secret123"})
        assert r.status_code == 200

    def test_auth_health_check_bypassed(self, tmp_path: Path) -> None:
        auth = AuthConfig(enabled=True, api_key="secret123")
        app = create_app(project_root=tmp_path, auth_config=auth)
        client = TestClient(app)
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_auth_wrong_key(self, tmp_path: Path) -> None:
        auth = AuthConfig(enabled=True, api_key="secret123")
        app = create_app(project_root=tmp_path, auth_config=auth)
        client = TestClient(app)
        r = client.get("/api/agents", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_auth_pages_protected(self, tmp_path: Path) -> None:
        auth = AuthConfig(enabled=True, api_key="secret123")
        app = create_app(project_root=tmp_path, auth_config=auth)
        client = TestClient(app)
        r = client.get("/")
        assert r.status_code == 401

    def test_auth_pages_with_key(self, tmp_path: Path) -> None:
        auth = AuthConfig(enabled=True, api_key="secret123")
        app = create_app(project_root=tmp_path, auth_config=auth)
        client = TestClient(app)
        r = client.get("/", headers={"X-API-Key": "secret123"})
        assert r.status_code == 200


class TestAuthSingleton:
    """Tests for global auth config management."""

    def test_get_auth_config_default(self) -> None:
        config = get_auth_config()
        assert config.enabled is False

    def test_set_and_get(self) -> None:
        custom = AuthConfig(enabled=True, api_key="test")
        set_auth_config(custom)
        assert get_auth_config() is custom

    def test_reset(self) -> None:
        set_auth_config(AuthConfig(enabled=True, api_key="test"))
        reset_auth_config()
        config = get_auth_config()
        assert config.enabled is False
