"""Tests for encrypted SQLite LLM secret store."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.platform import LocalTenant
from forge_agent.web.llm_settings import get_llm_settings_view, save_api_key
from forge_agent.web.secret_store import get_secret_store


@pytest.fixture
def tenant_project(tmp_path: Path) -> tuple[LocalTenant, Path]:
    root = tmp_path / "data"
    tenant = LocalTenant("acme", root_dir=root)
    project_root = tenant.create_project("demo")
    return tenant, project_root


class TestSecretStore:
    def test_save_api_key_to_database_not_project_env(
        self, tenant_project: tuple[LocalTenant, Path]
    ) -> None:
        tenant, project_root = tenant_project
        result = save_api_key(tenant, project_root, "DEEPSEEK_API_KEY", "sk-test-key")
        assert result["storage"] == "database"
        assert not (project_root / ".env").exists()

        store = get_secret_store(tenant.root_dir)
        assert store.get_key(tenant.tenant_id, "demo", "DEEPSEEK_API_KEY") == "sk-test-key"

        view = get_llm_settings_view(tenant, "demo")
        deepseek = next(p for p in view["providers"] if p["provider_id"] == "deepseek")
        assert deepseek["key_configured"] is True
        assert view["key_storage"] == "database"

    def test_key_survives_reload(self, tenant_project: tuple[LocalTenant, Path]) -> None:
        tenant, project_root = tenant_project
        save_api_key(tenant, project_root, "DEEPSEEK_API_KEY", "sk-persist")
        store2 = get_secret_store(tenant.root_dir)
        assert store2.get_key(tenant.tenant_id, "demo", "DEEPSEEK_API_KEY") == "sk-persist"

    def test_needs_setup_when_primary_missing_key(
        self, tenant_project: tuple[LocalTenant, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        tenant, _ = tenant_project
        view = get_llm_settings_view(tenant, "demo")
        assert view["needs_setup"] is True
