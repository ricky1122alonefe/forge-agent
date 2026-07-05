"""Tests for tenant agent type storage (A5.1/A5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.builtin.agent_type_registry import AgentTypeNotFoundError
from forge_agent.builtin.tenant_types import (
    delete_tenant_agent_type,
    save_tenant_agent_type,
    tenant_agent_types_dir,
)
from forge_agent.platform.local_tenant import LocalTenant


@pytest.fixture
def tenant(tmp_path: Path) -> LocalTenant:
    return LocalTenant("acme", root_dir=tmp_path / "data")


def _sample_type(type_id: str = "custom_analyst") -> dict:
    return {
        "type_id": type_id,
        "name": "Custom Analyst",
        "description": "Tenant custom type",
        "domain": "generic",
        "template": "prompt_agent",
        "params": [{"name": "topic", "type": "string", "required": True, "description": "Topic"}],
        "prompt_template": "Analyze {topic}",
        "output_schema": {"type": "object", "properties": {"verdict": {"type": "string"}}},
        "output_mapping": {"verdict": "verdict"},
    }


class TestTenantTypes:
    def test_save_and_load_via_registry(self, tenant: LocalTenant) -> None:
        save_tenant_agent_type(tenant, _sample_type())
        registry = AgentTypeRegistry(tenant_shared_dir=tenant_agent_types_dir(tenant))
        loaded = registry.get("custom_analyst")
        assert loaded["name"] == "Custom Analyst"
        sources = {t["type_id"]: t["source"] for t in registry.list_with_source()}
        assert sources["custom_analyst"] == "tenant"

    def test_delete_tenant_type(self, tenant: LocalTenant) -> None:
        save_tenant_agent_type(tenant, _sample_type())
        assert delete_tenant_agent_type(tenant, "custom_analyst") is True
        registry = AgentTypeRegistry(tenant_shared_dir=tenant_agent_types_dir(tenant))
        with pytest.raises(AgentTypeNotFoundError):
            registry.get("custom_analyst")

    def test_invalid_type_id_rejected(self, tenant: LocalTenant) -> None:
        bad = _sample_type("Bad-ID")
        with pytest.raises(ValueError):
            save_tenant_agent_type(tenant, bad)

    def test_persisted_yaml_shape(self, tenant: LocalTenant) -> None:
        path = save_tenant_agent_type(tenant, _sample_type("risk_bot"))
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["agent_type"]["type_id"] == "risk_bot"
