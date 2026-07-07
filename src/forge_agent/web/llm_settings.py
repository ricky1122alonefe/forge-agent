"""Web helpers for tenant/project LLM configuration (P3.3)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from forge_agent.platform import LLMConfigManager, LocalTenant
from forge_agent.platform.llm_config import deep_merge
from forge_agent.web.secret_store import get_secret_store

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def tenant_env_path(tenant: LocalTenant) -> Path:
    return tenant.tenant_dir / ".env"


def project_env_path(project_root: Path) -> Path:
    return project_root / ".env"


def load_env_files(tenant: LocalTenant, project_root: Path) -> None:
    """Load tenant/project .env into process environment (legacy; does not override existing)."""
    for path in (tenant_env_path(tenant), project_env_path(project_root)):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def bootstrap_project_secrets(tenant: LocalTenant, project_root: Path) -> None:
    """Load DB-stored keys (preferred) then legacy .env files into os.environ."""
    load_env_files(tenant, project_root)
    store = get_secret_store(tenant.root_dir)
    store.apply_to_environment(tenant.tenant_id, project_root.name)


def _key_configured(
    tenant: LocalTenant,
    project_id: str,
    env_name: str | None,
    alt_envs: list[str],
) -> bool:
    names = [env_name, *alt_envs] if env_name else list(alt_envs)
    store = get_secret_store(tenant.root_dir)
    for name in names:
        if not name:
            continue
        if store.has_key(tenant.tenant_id, project_id, name):
            return True
        if os.environ.get(name):
            return True
    return False


def get_llm_settings_view(tenant: LocalTenant, project_id: str) -> dict[str, Any]:
    """Return LLM settings for the web UI (never includes raw API keys)."""
    bootstrap_project_secrets(tenant, tenant.get_project_path(project_id))
    manager = LLMConfigManager(tenant)
    cfg = manager.load(project_id)
    providers: list[dict[str, Any]] = []
    for pid, provider in cfg.providers.items():
        needs_key = provider.type not in {"ollama", "mock"}
        key_ok = _key_configured(tenant, project_id, provider.api_key_env, provider.alt_envs)
        providers.append(
            {
                "provider_id": pid,
                "type": provider.type,
                "model": provider.model,
                "base_url": provider.base_url,
                "api_key_env": provider.api_key_env,
                "enabled": provider.enabled,
                "is_primary": pid == cfg.primary_id,
                "key_configured": key_ok or not needs_key,
                "needs_key": needs_key,
                "tags": provider.tags,
            }
        )
    primary = cfg.providers.get(cfg.primary_id) if cfg.primary_id else None
    primary_needs_key = bool(
        primary and primary.type not in {"ollama", "mock"} and primary.api_key_env
    )
    primary_key_ok = (
        not primary_needs_key
        or _key_configured(tenant, project_id, primary.api_key_env, primary.alt_envs)
        if primary
        else True
    )
    store = get_secret_store(tenant.root_dir)
    return {
        "tenant_id": tenant.tenant_id,
        "project_id": project_id,
        "primary_id": cfg.primary_id,
        "predict_mode": cfg.predict_mode,
        "source_path": str(cfg.source_path) if cfg.source_path else None,
        "providers": providers,
        "needs_setup": primary_needs_key and not primary_key_ok,
        "key_storage": "database",
        "secrets_db": str(store.db_path),
        "env_files": {
            "tenant": str(tenant_env_path(tenant)),
            "project": str(project_env_path(tenant.get_project_path(project_id))),
        },
    }


def save_api_key(
    tenant: LocalTenant,
    project_root: Path,
    env_name: str,
    api_key: str,
) -> dict[str, Any]:
    """Persist an API key to the encrypted SQLite store (not project files)."""
    env_name = env_name.strip()
    if not env_name or not api_key.strip():
        raise ValueError("env_name and api_key are required")
    store = get_secret_store(tenant.root_dir)
    store.set_key(tenant.tenant_id, project_root.name, env_name, api_key)
    return {
        "storage": "database",
        "db_path": str(store.db_path),
        "env_name": env_name,
    }


def delete_api_key(tenant: LocalTenant, project_root: Path, env_name: str) -> None:
    store = get_secret_store(tenant.root_dir)
    store.delete_key(tenant.tenant_id, project_root.name, env_name)
    os.environ.pop(env_name.strip(), None)


def update_llm_config(
    tenant: LocalTenant,
    project_id: str,
    *,
    primary_id: str | None = None,
    provider_updates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Merge provider settings into project-level llm_providers.json."""
    manager = LLMConfigManager(tenant)
    path = manager.project_config_path(project_id)
    data = {}
    if path.is_file():
        import json

        data = json.loads(path.read_text(encoding="utf-8"))

    if primary_id:
        data["primary_id"] = primary_id

    if provider_updates:
        providers = data.setdefault("providers", {})
        for pid, patch in provider_updates.items():
            entry = providers.setdefault(pid, {"type": pid})
            entry.update({k: v for k, v in patch.items() if v is not None})

    manager.save_project(project_id, data)
    return get_llm_settings_view(tenant, project_id)


def merge_effective_config_data(tenant: LocalTenant, project_id: str) -> dict[str, Any]:
    """Return raw merged config dict (for tests)."""
    import json

    from forge_agent.llm.config import BUILTIN_DEFAULTS

    manager = LLMConfigManager(tenant)
    data = json.loads(json.dumps(BUILTIN_DEFAULTS))
    tenant_path = manager.tenant_config_path
    if tenant_path.is_file():
        data = deep_merge(data, json.loads(tenant_path.read_text(encoding="utf-8")))
    project_path = manager.project_config_path(project_id)
    if project_path.is_file():
        data = deep_merge(data, json.loads(project_path.read_text(encoding="utf-8")))
    return data
