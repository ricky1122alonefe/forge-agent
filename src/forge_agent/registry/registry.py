"""AgentRegistry — singleton registry for Agent classes & instances.

Responsibilities:
    1. Register/unregister Agent classes (typically via @register_agent).
    2. Lazily instantiate and initialize Agents.
    3. Query by id / domain / tag.
    4. Manage lifecycle (initialize / shutdown_all).
    5. Support hot-reload & dynamic injection (v0.2+ generator will use this).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from forge_agent.core.base import BaseAgent

log = logging.getLogger(__name__)


class AgentRegistry:
    """Process-wide singleton registry.

    Thread-safety: instance creation guarded by an asyncio.Lock.
    """

    _instance: AgentRegistry | None = None

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._classes: dict[str, type[BaseAgent]] = {}
        self._instances: dict[str, BaseAgent] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._initialized = True
        log.info("AgentRegistry initialized.")

    # ------------------------------------------------------------------ Register

    def register(
        self,
        agent_cls: type[BaseAgent],
        *,
        domain: str | None = None,
        tags: list[str] | None = None,
        override: bool = False,
    ) -> None:
        from forge_agent.exceptions import DuplicateRegistrationError

        agent_id = getattr(agent_cls, "agent_id", None)
        if not agent_id:
            raise ValueError(f"Class {agent_cls.__name__} has no agent_id. Set it as a ClassVar.")
        if agent_id in self._classes and not override:
            raise DuplicateRegistrationError(agent_id)
        self._classes[agent_id] = agent_cls
        self._metadata[agent_id] = {
            "domain": domain or getattr(agent_cls, "domain", "generic"),
            "tags": list(tags or []),
            "version": getattr(agent_cls, "version", "0.1.0"),
            "class_name": agent_cls.__name__,
        }
        log.info("Registered agent: %s (domain=%s)", agent_id, self._metadata[agent_id]["domain"])

    def unregister(self, agent_id: str) -> None:
        """Unregister a class; if instance exists, schedule shutdown."""
        if agent_id in self._instances:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    task = loop.create_task(self._instances[agent_id].shutdown())
                    task.add_done_callback(lambda _: None)
            except RuntimeError:
                pass
        self._classes.pop(agent_id, None)
        self._instances.pop(agent_id, None)
        self._metadata.pop(agent_id, None)
        log.info("Unregistered agent: %s", agent_id)

    # ------------------------------------------------------------------ Lookup

    async def get(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        force_new: bool = False,
    ) -> BaseAgent:
        """Get a (cached) Agent instance, initializing it on first access."""
        if not force_new and agent_id in self._instances:
            return self._instances[agent_id]
        async with self._lock:
            if not force_new and agent_id in self._instances:
                return self._instances[agent_id]
            if agent_id not in self._classes:
                from forge_agent.exceptions import AgentNotFoundError

                raise AgentNotFoundError(agent_id, available=list(self._classes.keys()))
            instance = self._classes[agent_id](config=config)
            await instance.initialize()
            self._instances[agent_id] = instance
            return instance

    async def get_many(
        self,
        agent_ids: list[str],
        *,
        shared_config: dict[str, Any] | None = None,
    ) -> list[BaseAgent]:
        """Get many agents concurrently — useful for parallel pipeline stages."""
        return list(
            await asyncio.gather(*[self.get(aid, config=shared_config) for aid in agent_ids])
        )

    # ------------------------------------------------------------------ Query

    def list(
        self,
        *,
        domain: str | None = None,
        tag: str | None = None,
    ) -> list[str]:
        ids = list(self._classes.keys())
        if domain:
            ids = [i for i in ids if self._metadata[i]["domain"] == domain]
        if tag:
            ids = [i for i in ids if tag in self._metadata[i]["tags"]]
        return ids

    def get_metadata(self, agent_id: str) -> dict[str, Any]:
        return dict(self._metadata.get(agent_id, {}))

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._classes

    def __len__(self) -> int:
        return len(self._classes)

    # ------------------------------------------------------------------ Lifecycle

    async def shutdown_all(self) -> None:
        for inst in list(self._instances.values()):
            try:
                await inst.shutdown()
            except Exception:
                log.exception("Error shutting down %s", inst.agent_id)
        self._instances.clear()


def get_registry() -> AgentRegistry:
    """Module-level convenience accessor for the singleton."""
    return AgentRegistry()
