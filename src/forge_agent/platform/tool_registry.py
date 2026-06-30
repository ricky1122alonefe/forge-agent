"""Tool registry for built-in and tenant-scoped tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge_agent.exceptions import ForgeError
from forge_agent.platform.tool import Tool


class ToolNotFoundError(ForgeError, KeyError):
    """Raised when a tool name is not registered."""

    default_hint = "Run 'forge-agent tools' to see available tools."

    def __init__(
        self, tool_name: str, *, available: list[str] | None = None, hint: str | None = None
    ) -> None:
        msg = f"Tool {tool_name!r} not found"
        if available:
            msg += f". Available: {sorted(available)}"
        super().__init__(f"{msg}.", hint=hint)
        self.tool_name = tool_name


class ToolRegistry:
    """Registry of tools available to agents.

    Tools can be registered programmatically or discovered from YAML manifests
    in tenant shared directories.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Return a registered tool."""
        if name not in self._tools:
            raise ToolNotFoundError(name, available=list(self._tools))
        return self._tools[name]

    def list(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """Return names of all registered tools."""
        return sorted(self._tools)

    def load_manifest(self, path: Path) -> None:
        """Load tool manifests from a YAML file.

        The manifest is informational only; handlers must be registered
        programmatically. This method validates the manifest and stores
        metadata entries as tools with no-op handlers if not already present.
        """
        if not path.exists():
            return
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in data.get("tools", []):
            name = entry.get("name")
            if name and name not in self._tools:
                self.register(
                    Tool(
                        name=name,
                        description=entry.get("description", ""),
                        handler=_noop_tool,
                        params=entry.get("params", {}),
                        tags=entry.get("tags", []),
                    )
                )


async def _noop_tool(**kwargs: Any) -> dict[str, Any]:
    """Placeholder handler for manifest-only tools."""
    return {"note": "Tool handler not implemented", "input": kwargs}


# Global singleton for the active process.
_GLOBAL_REGISTRY: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry, creating it if necessary."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ToolRegistry()
    return _GLOBAL_REGISTRY


def reset_tool_registry() -> ToolRegistry:
    """Reset and return the global tool registry."""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = ToolRegistry()
    return _GLOBAL_REGISTRY
