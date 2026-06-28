"""Agent templates — pre-built agent behaviors that can be instantiated from config.

A template is a BaseAgent subclass whose observe/decide/act behavior is driven by
configuration rather than hard-coded Python logic.  The AgentFactory turns a config
dict (usually from YAML) into a registered agent class.
"""

from __future__ import annotations

from forge_agent.core.templates.prompt_agent import PromptAgent

__all__ = ["PromptAgent"]
