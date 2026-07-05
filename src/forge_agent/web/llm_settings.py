"""Web helpers for tenant/project LLM configuration (P3.3)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from forge_agent.platform import LLMConfigManager, LocalTenant
from forge_agent.platform.llm_config import deep_merge

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def tenant_env_path(tenant: LocalTenant) -> Path:
    return tenant.tenant_dir / ".env"


def project_env_path(project_root: Path) -> Path:
    return project_root / ".env"


def load_env_files(tenant: LocalTenant, project_root: Path) -> None:
    """Load tenant/project .env into process environment (does not override existing)."""
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


def _key_configured(env_name: str | None, alt_envs: list[str]) -> bool:
    names = [env_name, *alt_envs] if env_name else list(alt_envs)
    return any(name and os.environ.get(name) for name in names)


def get_llm_settings_view(tenant: LocalTenant, project_id: str) -> dict[str, Any]:
    """Return LLM settings for the web UI (never includes raw API keys)."""
    manager = LLMConfigManager(tenant)
    cfg = manager.load(project_id)
    providers: list[dict[str, Any]] = []
    for pid, provider in cfg.providers.items():
        needs_key = provider.type not in {"ollama", "mock"}
        providers.append(
            {
                "provider_id": pid,
                "type": provider.type,
                "model": provider.model,
                "base_url": provider.base_url,
                "api_key_env": provider.api_key_env,
                "enabled": provider.enabled,
                "is_primary": pid == cfg.primary_id,
                "key_configured": _key_configured(provider.api_key_env, provider.alt_envs)
                or not needs_key,
                "needs_key": needs_key,
                "tags": provider.tags,
            }
        )
    return {
        "tenant_id": tenant.tenant_id,
        "project_id": project_id,
        "primary_id": cfg.primary_id,
        "predict_mode": cfg.predict_mode,
        "source_path": str(cfg.source_path) if cfg.source_path else None,
        "providers": providers,
        "env_files": {
            "tenant": str(tenant_env_path(tenant)),
            "project": str(project_env_path(tenant.get_project_path(project_id))),
        },
    }


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# forge-agent API keys (do not commit)", ""]
    for key in sorted(values):
        if values[key]:
            lines.append(f'{key}="{values[key]}"')
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def save_api_key(tenant: LocalTenant, project_root: Path, env_name: str, api_key: str) -> Path:
    """Persist an API key to the project .env file."""
    env_name = env_name.strip()
    if not env_name or not api_key.strip():
        raise ValueError("env_name and api_key are required")
    path = project_env_path(project_root)
    values = _read_env_file(path)
    values[env_name] = api_key.strip()
    _write_env_file(path, values)
    os.environ[env_name] = api_key.strip()
    return path


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
