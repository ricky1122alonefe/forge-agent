"""Registry: agent registration, lookup, and lifecycle management."""

from __future__ import annotations

from forge_agent.registry.decorators import register_agent
from forge_agent.registry.registry import AgentRegistry, get_registry

__all__ = ["AgentRegistry", "get_registry", "register_agent"]
