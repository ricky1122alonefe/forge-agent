"""Resolve project-scoped LLM chat for web AgentSpec generation (A4.2)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from forge_agent.llm.registry import get_registry
from forge_agent.platform import LLMConfigManager, LocalTenant
from forge_agent.web.llm_settings import bootstrap_project_secrets

LLMChatFn = Callable[..., Awaitable[Any]]


def configure_project_llm(tenant: LocalTenant, project_root) -> None:
    """Load tenant/project LLM config into the process registry."""
    bootstrap_project_secrets(tenant, project_root)
    cfg = LLMConfigManager(tenant).load(project_root.name)
    get_registry().configure(cfg)


def resolve_llm_chat(tenant: LocalTenant, project_root) -> LLMChatFn | None:
    """Return an async chat callable when a primary provider is configured."""
    configure_project_llm(tenant, project_root)
    cfg = LLMConfigManager(tenant).load(project_root.name)
    if not cfg.primary_id:
        return None

    async def _chat(messages, **kwargs):
        from forge_agent.llm.protocol import chat

        return await chat(messages, **kwargs)

    return _chat
