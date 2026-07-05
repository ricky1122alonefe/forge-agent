"""Unit tests for web auth service."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.platform import LocalTenant
from forge_agent.web.auth.config import WebAuthConfig
from forge_agent.web.auth.service import AuthService


@pytest.fixture
def auth_service(tmp_path: Path) -> tuple[AuthService, Path]:
    root = tmp_path / "data"
    config = WebAuthConfig(enabled=True, session_secret="unit-test-secret")
    return AuthService(root, config), root


class TestAuthService:
    def test_register_creates_tenant_and_default_project(
        self, auth_service: tuple[AuthService, Path]
    ) -> None:
        service, root = auth_service
        user, session_id = service.register("alice", "password123")
        assert user.username == "alice"
        assert user.tenant_id == "alice"
        assert session_id
        tenant = LocalTenant("alice", root_dir=root)
        assert tenant.project_exists("default")

    def test_login_after_register(self, auth_service: tuple[AuthService, Path]) -> None:
        service, _ = auth_service
        service.register("bob", "password123")
        user, session_id = service.login("bob", "password123")
        assert user.username == "bob"
        assert session_id

    def test_login_wrong_password(self, auth_service: tuple[AuthService, Path]) -> None:
        service, _ = auth_service
        service.register("carol", "password123")
        with pytest.raises(ValueError, match="用户名或密码错误"):
            service.login("carol", "wrong-password")

    def test_tenant_access_control(self, auth_service: tuple[AuthService, Path]) -> None:
        service, _ = auth_service
        user, session_id = service.register("dave", "password123")
        assert service.user_can_access_tenant(user, "dave")
        assert not service.user_can_access_tenant(user, "other")
        loaded = service.get_user_for_session(session_id)
        assert loaded is not None
        assert loaded.username == "dave"
