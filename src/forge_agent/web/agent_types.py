"""Web helpers for AgentTypeRegistry (AGENT_PLAN A5)."""

from __future__ import annotations

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.builtin.tenant_types import tenant_agent_types_dir
from forge_agent.web.context import ProjectContext


def registry_for(ctx: ProjectContext) -> AgentTypeRegistry:
    """Load built-in + tenant agent types for a project context."""
    return AgentTypeRegistry(tenant_shared_dir=tenant_agent_types_dir(ctx.tenant))
