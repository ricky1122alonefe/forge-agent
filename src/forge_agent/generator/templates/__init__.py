"""Code templates for each AgentType.

Templates are skeleton code that serve as few-shot examples for the LLM,
helping it generate code that matches the type's typical structure.

Usage::

    from forge_agent.generator.templates import get_template

    skeleton = get_template(AgentType.SCRAPER)
"""

from __future__ import annotations

import logging
from pathlib import Path

from forge_agent.core.agent_type import AgentType

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent
_CACHE: dict[AgentType, str] = {}


def get_template(agent_type: AgentType) -> str | None:
    """Load the code template for a given AgentType.

    Returns the template string, or None if no template file exists.
    Templates are cached after first load.
    """
    if agent_type in _CACHE:
        return _CACHE[agent_type]

    filename = f"{agent_type.value}.py.tmpl"
    path = _TEMPLATES_DIR / filename
    if not path.exists():
        log.debug("No template found for %s (%s)", agent_type.value, path)
        return None

    content = path.read_text(encoding="utf-8")
    _CACHE[agent_type] = content
    return content


def list_templates() -> dict[AgentType, bool]:
    """Check which AgentTypes have template files."""
    result: dict[AgentType, bool] = {}
    for at in AgentType:
        result[at] = (_TEMPLATES_DIR / f"{at.value}.py.tmpl").exists()
    return result


def clear_cache() -> None:
    """Clear the template cache (useful for tests)."""
    _CACHE.clear()
