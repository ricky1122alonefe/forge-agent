"""Multi-tenant LLM configuration loader.

Configuration is resolved in three layers:

1. Built-in defaults (``deepseek`` + ``ollama`` + common providers)
2. Tenant-level ``~/.forge-agent/tenants/{tenant}/llm_providers.json``
3. Project-level ``~/.forge-agent/tenants/{tenant}/projects/{project}/llm_providers.json``

Each layer overrides the previous one recursively, so a project can change only
its ``primary_id`` while inheriting all providers from the tenant and defaults.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from forge_agent.llm.config import LLMConfig, ProviderConfig
from forge_agent.platform.tenant import Tenant

log = logging.getLogger(__name__)

LLM_CONFIG_FILE = "llm_providers.json"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``.

    Dicts are merged; all other values are replaced.
    """
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_llm_config(data: dict[str, Any]) -> LLMConfig:
    """Build an ``LLMConfig`` from a merged dictionary."""
    providers: dict[str, ProviderConfig] = {}
    for provider_id, provider_data in (data.get("providers") or {}).items():
        if not isinstance(provider_data, dict):
            continue
        providers[provider_id] = ProviderConfig.from_dict(provider_id, provider_data)
    return LLMConfig(
        primary_id=str(data.get("primary_id", "deepseek")),
        predict_mode=str(data.get("predict_mode", "single")),
        providers=providers,
        multi=dict(data.get("multi") or {}),
    )


class LLMConfigManager:
    """Loads and persists layered LLM configuration for a tenant."""

    def __init__(self, tenant: Tenant) -> None:
        self.tenant = tenant

    @property
    def tenant_config_path(self) -> Path:
        """Tenant-level config file path.

        For ``LocalTenant`` this is ``{tenant_dir}/llm_providers.json``.
        """
        return Path(self.tenant.get_config_path()).parent / LLM_CONFIG_FILE

    def project_config_path(self, project_id: str) -> Path:
        """Project-level config file path."""
        return self.tenant.get_project_path(project_id) / LLM_CONFIG_FILE

    def load(self, project_id: str | None = None) -> LLMConfig:
        """Load effective config from built-in defaults + tenant + project."""
        from forge_agent.llm.config import BUILTIN_DEFAULTS

        data = json.loads(json.dumps(BUILTIN_DEFAULTS))
        sources = ["built-in defaults"]

        tenant_path = self.tenant_config_path
        if tenant_path.is_file():
            tenant_data = json.loads(tenant_path.read_text(encoding="utf-8"))
            data = deep_merge(data, tenant_data)
            sources.append(str(tenant_path))

        if project_id is not None and self.tenant.project_exists(project_id):
            project_path = self.project_config_path(project_id)
            if project_path.is_file():
                project_data = json.loads(project_path.read_text(encoding="utf-8"))
                data = deep_merge(data, project_data)
                sources.append(str(project_path))

        cfg = _parse_llm_config(data)
        if sources[-1] == "built-in defaults":
            cfg.source_path = None
        else:
            cfg.source_path = Path(sources[-1])
        log.info(
            "LLM config loaded for tenant=%s project=%s from %s",
            self.tenant.tenant_id,
            project_id or "(tenant-level)",
            cfg.source_path,
        )
        return cfg

    def save_tenant(self, data: dict[str, Any]) -> None:
        """Persist raw config dict at the tenant level."""
        self.tenant_config_path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def save_project(self, project_id: str, data: dict[str, Any]) -> None:
        """Persist raw config dict at the project level."""
        path = self.project_config_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def load_tenant_project_config(tenant: Tenant, project_id: str | None = None) -> LLMConfig:
    """Convenience wrapper: load layered config for a tenant/project."""
    return LLMConfigManager(tenant).load(project_id)
