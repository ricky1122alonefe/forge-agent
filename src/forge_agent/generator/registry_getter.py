"""Lazy import helper to avoid circular dependency between generator/ and registry/."""

from __future__ import annotations

from typing import Any


def get_registry_lazy() -> Any:
    """Return the global AgentRegistry without creating an import cycle."""
    from forge_agent.registry.registry import AgentRegistry

    return AgentRegistry()
