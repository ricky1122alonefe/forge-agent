"""PromptProvider Protocol — pluggable prompt sources.

Three built-in providers:
1. DefaultPromptProvider — hardcoded prompts (current behavior)
2. FilePromptProvider    — load from .forge_agent/prompts/ directory
3. ChainPromptProvider   — chain multiple providers, first hit wins

Usage::

    from forge_agent.generator.prompt_provider import (
        DefaultPromptProvider,
        FilePromptProvider,
        ChainPromptProvider,
        get_prompt_provider,
    )

    # Use defaults
    provider = get_prompt_provider()
    system = provider.get_system_prompt(AgentType.SCRAPER)

    # Use file overrides
    provider = ChainPromptProvider(
        [
            FilePromptProvider("./prompts/"),
            DefaultPromptProvider(),
        ]
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from forge_agent.core.agent_type import AgentType

log = logging.getLogger(__name__)


@runtime_checkable
class PromptProvider(Protocol):
    """Protocol for prompt sources.

    Any object implementing these two methods can serve as a PromptProvider.
    """

    def get_system_prompt(self, agent_type: AgentType) -> str:
        """Return the system prompt for a given agent type."""
        ...

    def get_user_prompt_template(self, agent_type: AgentType) -> str | None:
        """Return an optional user prompt template, or None."""
        ...


# ------------------------------------------------------------------ Default


class DefaultPromptProvider:
    """Uses the built-in hardcoded prompts from prompts.py."""

    def get_system_prompt(self, agent_type: AgentType) -> str:
        from forge_agent.generator.prompts import get_system_prompt

        return get_system_prompt(agent_type)

    def get_user_prompt_template(self, agent_type: AgentType) -> str | None:
        return None  # No override; use build_user_prompt() default


# ------------------------------------------------------------------ File


class FilePromptProvider:
    """Loads prompts from files on disk.

    Directory structure::

        <base_dir>/
            scraper.system.txt
            analyzer.system.txt
            monitor.system.txt
            generator.system.txt
            general.system.txt
            scraper.user.txt       (optional)
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def get_system_prompt(self, agent_type: AgentType) -> str:
        path = self.base_dir / f"{agent_type.value}.system.txt"
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                log.debug("Loaded system prompt from %s", path)
                return content
        # Fallback to default
        from forge_agent.generator.prompts import get_system_prompt

        return get_system_prompt(agent_type)

    def get_user_prompt_template(self, agent_type: AgentType) -> str | None:
        path = self.base_dir / f"{agent_type.value}.user.txt"
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                return content
        return None


# ------------------------------------------------------------------ Chain


class ChainPromptProvider:
    """Chains multiple providers; first non-None result wins.

    For system prompts, always returns a string (falls back through chain).
    For user prompt templates, returns first non-None.
    """

    def __init__(self, providers: list[PromptProvider]) -> None:
        self.providers = providers

    def get_system_prompt(self, agent_type: AgentType) -> str:
        for provider in self.providers:
            try:
                result = provider.get_system_prompt(agent_type)
                if result:
                    return result
            except Exception:
                log.debug(
                    "PromptProvider %s failed for %s", type(provider).__name__, agent_type.value
                )
        # Ultimate fallback
        from forge_agent.generator.prompts import get_system_prompt

        return get_system_prompt(agent_type)

    def get_user_prompt_template(self, agent_type: AgentType) -> str | None:
        for provider in self.providers:
            try:
                result = provider.get_user_prompt_template(agent_type)
                if result is not None:
                    return result
            except Exception:
                log.debug(
                    "PromptProvider %s failed for %s", type(provider).__name__, agent_type.value
                )
        return None


# ------------------------------------------------------------------ Factory

_provider: PromptProvider | None = None


def get_prompt_provider() -> PromptProvider:
    """Get the global PromptProvider singleton."""
    global _provider
    if _provider is None:
        _provider = DefaultPromptProvider()
    return _provider


def set_prompt_provider(provider: PromptProvider) -> None:
    """Set the global PromptProvider."""
    global _provider
    _provider = provider


def reset_prompt_provider() -> None:
    """Reset to default provider."""
    global _provider
    _provider = None
