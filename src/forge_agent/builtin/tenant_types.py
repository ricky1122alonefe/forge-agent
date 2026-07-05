"""Tenant-scoped agent type storage helpers (AGENT_PLAN A5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge_agent.platform import LocalTenant

RESERVED_TYPE_IDS = frozenset({"chief"})


def tenant_agent_types_dir(tenant: LocalTenant) -> Path:
    """Return (and ensure) tenants/{id}/shared/agent_types/."""
    path = tenant.get_shared_path() / "agent_types"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tenant_type_path(tenant: LocalTenant, type_id: str) -> Path:
    return tenant_agent_types_dir(tenant) / f"{type_id}.yaml"


def list_tenant_type_ids(tenant: LocalTenant) -> list[str]:
    directory = tenant_agent_types_dir(tenant)
    return sorted(path.stem for path in directory.glob("*.yaml") if not path.name.startswith("_"))


def validate_agent_type_def(type_def: dict[str, Any]) -> None:
    """Validate a tenant agent type payload before persistence."""
    if not isinstance(type_def, dict):
        raise ValueError("agent_type must be a mapping")
    type_id = str(type_def.get("type_id", "")).strip()
    if not type_id:
        raise ValueError("type_id is required")
    if type_id in RESERVED_TYPE_IDS:
        raise ValueError(f"type_id {type_id!r} is reserved")
    if not re_safe_type_id(type_id):
        raise ValueError("type_id must match [a-z][a-z0-9_]*")
    for key in ("name", "description", "domain", "template", "prompt_template"):
        if not str(type_def.get(key, "")).strip():
            raise ValueError(f"{key} is required")
    if not isinstance(type_def.get("params", []), list):
        raise ValueError("params must be a list")
    if not isinstance(type_def.get("output_schema"), dict):
        raise ValueError("output_schema must be a mapping")
    if not isinstance(type_def.get("output_mapping"), dict):
        raise ValueError("output_mapping must be a mapping")
    if "capabilities" in type_def and not isinstance(type_def["capabilities"], dict):
        raise ValueError("capabilities must be a mapping when provided")


def re_safe_type_id(type_id: str) -> bool:
    import re

    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", type_id))


def save_tenant_agent_type(tenant: LocalTenant, type_def: dict[str, Any]) -> Path:
    """Persist a tenant agent type YAML (create or overwrite)."""
    validate_agent_type_def(type_def)
    path = tenant_type_path(tenant, str(type_def["type_id"]))
    path.write_text(
        yaml.safe_dump({"agent_type": type_def}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def delete_tenant_agent_type(tenant: LocalTenant, type_id: str) -> bool:
    """Delete a tenant agent type. Returns False if the file did not exist."""
    path = tenant_type_path(tenant, type_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


def load_tenant_agent_type(tenant: LocalTenant, type_id: str) -> dict[str, Any] | None:
    path = tenant_type_path(tenant, type_id)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    agent_type = data.get("agent_type")
    return agent_type if isinstance(agent_type, dict) else None
