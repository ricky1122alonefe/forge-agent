"""Registry for built-in and tenant-scoped agent types."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge_agent.exceptions import ForgeError


class AgentTypeNotFoundError(ForgeError, KeyError):
    """Raised when an agent type does not exist."""

    default_hint = "Run 'forge-agent agent-types' to see available types."

    def __init__(
        self, type_id: str, *, available: list[str] | None = None, hint: str | None = None
    ) -> None:
        msg = f"Agent type {type_id!r} not found"
        if available:
            msg += f". Available: {sorted(available)}"
        super().__init__(f"{msg}.", hint=hint)
        self.type_id = type_id


class AgentTypeRegistry:
    """Loads and indexes agent type definitions from built-in and tenant paths."""

    BUILTIN_TYPES_DIR = Path(__file__).parent / "agent_types"

    def __init__(self, tenant_shared_dir: Path | None = None) -> None:
        self._types: dict[str, dict[str, Any]] = {}
        self._tenant_shared_dir = tenant_shared_dir
        self._load_builtin()
        self._load_tenant_types()

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_builtin(self) -> None:
        if not self.BUILTIN_TYPES_DIR.exists():
            return
        for yaml_file in sorted(self.BUILTIN_TYPES_DIR.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            data = self._load_yaml(yaml_file)
            agent_type = data.get("agent_type")
            if not agent_type or "type_id" not in agent_type:
                continue
            self._types[agent_type["type_id"]] = agent_type

    def _load_tenant_types(self) -> None:
        if not self._tenant_shared_dir or not self._tenant_shared_dir.exists():
            return
        for yaml_file in sorted(self._tenant_shared_dir.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            data = self._load_yaml(yaml_file)
            agent_type = data.get("agent_type")
            if not agent_type or "type_id" not in agent_type:
                continue
            # Tenant types override built-in types with the same type_id.
            self._types[agent_type["type_id"]] = agent_type

    def list(self) -> list[dict[str, Any]]:
        """Return all registered agent type definitions."""
        return list(self._types.values())

    def get(self, type_id: str) -> dict[str, Any]:
        """Return a single agent type definition."""
        if type_id not in self._types:
            raise AgentTypeNotFoundError(type_id, available=list(self._types))
        return self._types[type_id]

    def list_type_ids(self) -> list[str]:
        """Return the type IDs of all registered agent types."""
        return sorted(self._types)
