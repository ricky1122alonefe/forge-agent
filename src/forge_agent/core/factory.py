"""AgentFactory — create and register agents from configuration.

This is the bridge between declarative configuration (YAML/JSON) and the
runtime AgentRegistry.  Given a config like:

    {
        "agent_id": "sports.news",
        "name": "赛事情报专家",
        "domain": "sports",
        "template": "prompt_agent",
        "config": { ... }
    }

the factory builds the appropriate BaseAgent subclass, registers it, and returns
the class.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from forge_agent.core.base import BaseAgent
from forge_agent.core.templates.prompt_agent import register_prompt_agent
from forge_agent.core.templates.search_agent import register_search_agent

log = logging.getLogger(__name__)


class AgentFactory:
    """Build agents from declarative configuration."""

    # template name -> builder callable
    _builders: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        # Register built-in templates lazily to avoid import side-effects.
        self._builders.setdefault("prompt_agent", register_prompt_agent)
        self._builders.setdefault("search_agent", register_search_agent)

    def register_template(
        self,
        name: str,
        builder: Any,
    ) -> None:
        """Register a custom agent template builder."""
        self._builders[name] = builder

    def from_dict(self, config: dict[str, Any]) -> type[BaseAgent]:
        """Create and register a single agent from a dict config."""
        agent_id = config["agent_id"]
        name = config.get("name", agent_id)
        domain = config.get("domain", "generic")
        template = config.get("template", "prompt_agent")
        version = config.get("version", "0.1.0")
        tags = config.get("tags")
        override = config.get("override", False)
        agent_config = config.get("config", {})

        builder = self._builders.get(template)
        if builder is None:
            msg = f"Unknown agent template: {template!r}. Available: {list(self._builders)}"
            raise ValueError(msg)

        cls = builder(
            agent_id=agent_id,
            name=name,
            domain=domain,
            config=agent_config,
            version=version,
            tags=tags,
            override=override,
        )
        log.info("Factory created agent %s from template %s", agent_id, template)
        return cls

    def load_yaml(self, path: str | Path) -> list[type[BaseAgent]]:
        """Load agent definitions from a YAML file.

        Supports two shapes:
            agents:
              - agent_id: ...
                ...
        or a top-level list:
            - agent_id: ...
              ...
        """
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return []

        agents_config: list[dict[str, Any]]
        if isinstance(data, dict) and "agents" in data:
            agents_config = data["agents"]
        elif isinstance(data, list):
            agents_config = data
        else:
            msg = "YAML must contain an 'agents:' list or be a top-level list"
            raise ValueError(msg)

        return [self.from_dict(cfg) for cfg in agents_config]

    def list_templates(self) -> list[str]:
        """Return names of registered agent templates."""
        return list(self._builders)
