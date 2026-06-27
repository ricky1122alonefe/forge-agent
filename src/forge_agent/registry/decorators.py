"""@register_agent decorator — the most common registration path."""

from __future__ import annotations

from typing import Any, Callable, Type

from forge_agent.core.base import BaseAgent
from forge_agent.registry.registry import get_registry


def register_agent(
    *,
    domain: str | None = None,
    tags: list[str] | None = None,
    override: bool = False,
) -> Callable[[Type[BaseAgent]], Type[BaseAgent]]:
    """Class decorator that registers a BaseAgent subclass with the global registry.

    Usage::

        @register_agent(domain="football", tags=["intel", "evidence"])
        class IntelAgent(BaseAgent):
            agent_id = "football.intel"
            name = "Football Intel Agent"
            ...

    Args:
        domain: Business domain tag (defaults to class attr).
        tags:   Free-form tags for filtering.
        override: Allow replacing an already-registered agent_id.
    """

    def decorator(cls: Type[BaseAgent]) -> Type[BaseAgent]:
        get_registry().register(cls, domain=domain, tags=tags, override=override)
        return cls

    return decorator
