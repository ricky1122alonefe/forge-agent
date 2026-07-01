"""Tests for forge_agent.platform.llm_config."""

from __future__ import annotations

import json

import pytest

from forge_agent.llm.config import LLMConfig
from forge_agent.platform import LLMConfigManager, LocalTenant, load_tenant_project_config
from forge_agent.platform.llm_config import deep_merge


@pytest.fixture
def manager(tmp_path):
    tenant = LocalTenant("acme", root_dir=tmp_path)
    return LLMConfigManager(tenant)


def test_deep_merge_replaces_and_preserves():
    base = {"providers": {"deepseek": {"model": "a", "enabled": True}}}
    override = {"providers": {"deepseek": {"model": "b"}, "openai": {"model": "c"}}}
    merged = deep_merge(base, override)
    assert merged["providers"]["deepseek"]["model"] == "b"
    assert merged["providers"]["deepseek"]["enabled"] is True
    assert merged["providers"]["openai"]["model"] == "c"


def test_load_builtin_defaults(manager):
    cfg = manager.load()
    assert isinstance(cfg, LLMConfig)
    assert cfg.primary_id == "deepseek"
    assert "deepseek" in cfg.providers
    assert "ollama" in cfg.providers


def test_tenant_override(manager):
    manager.save_tenant(
        {
            "primary_id": "openai",
            "providers": {
                "openai": {"type": "openai", "model": "gpt-4o"},
            },
        }
    )
    cfg = manager.load()
    assert cfg.primary_id == "openai"
    assert cfg.providers["openai"].model == "gpt-4o"
    # Deepseek remains from built-in defaults.
    assert "deepseek" in cfg.providers


def test_project_override(manager):
    manager.tenant.create_project("demo")
    manager.save_tenant({"primary_id": "openai"})
    manager.save_project(
        "demo",
        {
            "primary_id": "deepseek",
            "providers": {"deepseek": {"model": "deepseek-reasoner"}},
        },
    )
    cfg = manager.load("demo")
    assert cfg.primary_id == "deepseek"
    assert cfg.providers["deepseek"].model == "deepseek-reasoner"
    # Openai is inherited from tenant override.
    assert "openai" in cfg.providers


def test_project_does_not_affect_tenant(manager):
    manager.tenant.create_project("demo")
    manager.save_project(
        "demo",
        {
            "primary_id": "deepseek",
            "providers": {"deepseek": {"model": "deepseek-reasoner"}},
        },
    )
    cfg = manager.load()
    assert cfg.primary_id == "deepseek"  # built-in default
    assert cfg.providers["deepseek"].model == "deepseek-chat"


def test_load_tenant_project_config_wrapper(manager):
    manager.save_tenant({"primary_id": "openai"})
    cfg = load_tenant_project_config(manager.tenant)
    assert cfg.primary_id == "openai"


def test_save_tenant_creates_file(manager):
    manager.save_tenant({"primary_id": "openai"})
    assert manager.tenant_config_path.is_file()
    data = json.loads(manager.tenant_config_path.read_text(encoding="utf-8"))
    assert data["primary_id"] == "openai"


def test_save_project_creates_file(manager):
    manager.tenant.create_project("demo")
    manager.save_project("demo", {"primary_id": "deepseek"})
    path = manager.project_config_path("demo")
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["primary_id"] == "deepseek"
