"""Prompt optimizer — version & swap prompts based on reflection signals.

This is the **seed** of the self-iteration loop. v0.4 will wire it into a
background scheduler that triggers evolve() on agents whose reflection
score drops below threshold.
"""

from __future__ import annotations

import logging
from typing import Any

from forge_agent.core.capabilities import PromptManagerProtocol

log = logging.getLogger(__name__)


class PromptOptimizer:
    """Decide when a prompt needs a new version based on reflection signals."""

    def __init__(
        self,
        *,
        prompt_manager: PromptManagerProtocol,
        evolve_threshold: float = 0.3,
    ) -> None:
        self.prompt_manager = prompt_manager
        self.evolve_threshold = evolve_threshold

    def should_evolve(self, signal: dict[str, Any]) -> bool:
        return bool(signal.get("needs_evolve", False)) or float(
            signal.get("score", 1.0)
        ) < self.evolve_threshold

    def bump_version(
        self,
        agent_id: str,
        new_template: str,
        *,
        version: str | None = None,
    ) -> str:
        """Register a new prompt version; auto-increment if version is None."""
        if version is None:
            existing = self.prompt_manager.list_versions(agent_id)
            next_v = f"v{len(existing) + 1}"
            version = next_v
        self.prompt_manager.register(agent_id, version, new_template)
        log.info("PromptOptimizer: bumped %s → %s", agent_id, version)
        return version
