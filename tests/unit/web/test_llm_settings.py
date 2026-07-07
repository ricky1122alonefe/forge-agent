"""Tests for web LLM settings helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.platform import LocalTenant
from forge_agent.web.llm_settings import (
    get_llm_settings_view,
    save_api_key,
    update_llm_config,
)


@pytest.fixture
def tenant_project(tmp_path: Path) -> tuple[LocalTenant, Path]:
    root = tmp_path / "data"
    tenant = LocalTenant("acme", root_dir=root)
    project_root = tenant.create_project("demo")
    return tenant, project_root


class TestLLMSettings:
    def test_get_llm_settings_view(self, tenant_project: tuple[LocalTenant, Path]) -> None:
        tenant, _ = tenant_project
        view = get_llm_settings_view(tenant, "demo")
        assert view["tenant_id"] == "acme"
        assert view["project_id"] == "demo"
        assert any(p["provider_id"] == "deepseek" for p in view["providers"])
        assert view["key_storage"] == "database"

    def test_save_api_key_uses_database(self, tenant_project: tuple[LocalTenant, Path]) -> None:
        tenant, project_root = tenant_project
        result = save_api_key(tenant, project_root, "DEEPSEEK_API_KEY", "sk-test-key")
        assert result["storage"] == "database"
        assert not (project_root / ".env").exists()

        view = get_llm_settings_view(tenant, "demo")
        deepseek = next(p for p in view["providers"] if p["provider_id"] == "deepseek")
        assert deepseek["key_configured"] is True

    def test_update_llm_config_primary(self, tenant_project: tuple[LocalTenant, Path]) -> None:
        tenant, project_root = tenant_project
        view = update_llm_config(
            tenant, "demo", primary_id="ollama", provider_updates={"ollama": {"enabled": True}}
        )
        assert view["primary_id"] == "ollama"
        config_path = project_root / "llm_providers.json"
        assert config_path.exists()
