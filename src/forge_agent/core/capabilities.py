"""Pluggable capability protocols (Strategy interfaces).

The 5 required Agent capabilities (logging / searching / memory / reflection /
prompt management) are modeled as Protocols so users can plug in:

    - structlog / loguru / stdlib logging
    - Tavily / Bing / DuckDuckGo / self-hosted
    - Redis / SQLite / in-memory
    - Custom reflection strategies
    - File / DB / git-backed prompt stores

Default in-memory implementations live alongside this file.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

# ------------------------------------------------------------------ 1. Logger


@runtime_checkable
class LoggerProtocol(Protocol):
    """Minimal structured logger interface."""

    def log(
        self,
        level: str,
        agent_id: str,
        msg: str,
        **extra: Any,
    ) -> None: ...


class StdLogger:
    """Default logger for `BaseAgent` — thin adapter over the unified logger.

    The unified logger (structlog-backed) is configured once at CLI
    startup and uses `contextvars` for agent_id / run_id propagation.
    This class exists to satisfy `LoggerProtocol` and to be a
    drop-in replacement for any pre-existing user code that constructed
    a logger directly. New code should import from
    `forge_agent.observability.logger`.
    """

    def __init__(self, name: str = "forge_agent") -> None:
        # Local import to avoid a circular dep at module load time.
        from forge_agent.observability.logger import StructLogger

        self._impl = StructLogger(name=name)

    def log(
        self,
        level: str,
        agent_id: str,
        msg: str,
        **extra: Any,
    ) -> None:
        self._impl.log(level=level, agent_id=agent_id, msg=msg, **extra)


# ------------------------------------------------------------------ 2. Searcher


@runtime_checkable
class SearcherProtocol(Protocol):
    """Pluggable search interface (web / knowledge / vector)."""

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]: ...


class NoopSearcher:
    """Default no-op searcher — Agents that don't need search use this."""

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        return []


# ------------------------------------------------------------------ 3. Memory


@runtime_checkable
class MemoryProtocol(Protocol):
    """Long-term / short-term memory interface."""

    async def store(self, key: str, value: dict[str, Any]) -> None: ...
    async def retrieve(self, key: str) -> dict[str, Any] | None: ...
    async def query(self, **filters: Any) -> list[dict[str, Any]]: ...


class InMemoryStore:
    """In-process memory store (default; for dev & single-node runs)."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._order: deque[str] = deque(maxlen=max_size)

    async def store(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = {**value, "_stored_at": datetime.now(timezone.utc).isoformat()}
        self._order.append(key)

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        results = list(self._data.values())
        for k, v in filters.items():
            if isinstance(v, str):
                results = [r for r in results if str(r.get(k, "")) == v]
            elif callable(v):
                results = [r for r in results if v(r.get(k))]
        return results


# ------------------------------------------------------------------ 4. Reflection


@runtime_checkable
class ReflectionProtocol(Protocol):
    """Reflect on an execution to produce learning signals."""

    async def reflect(
        self,
        agent_id: str,
        context: dict[str, Any],
        observation: dict[str, Any],
        decision: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]: ...


class NoopReflector:
    """Default no-op reflector — Agents that don't need reflection use this."""

    async def reflect(
        self,
        agent_id: str,
        context: dict[str, Any],
        observation: dict[str, Any],
        decision: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "reflected": False,
            "score": 0.0,
            "notes": ["reflector not configured"],
        }


# ------------------------------------------------------------------ 5. Prompt Manager


@runtime_checkable
class PromptManagerProtocol(Protocol):
    """Manages versioned, renderable prompts per agent."""

    def get(self, agent_id: str, *, version: str | None = None) -> str: ...
    def render(
        self, agent_id: str, variables: dict[str, Any], *, version: str | None = None
    ) -> str: ...
    def list_versions(self, agent_id: str) -> list[str]: ...
    def register(self, agent_id: str, version: str, template: str) -> None: ...


class InMemoryPromptManager:
    """In-process prompt manager (default; replace with file/DB-backed)."""

    def __init__(self) -> None:
        self._prompts: dict[str, dict[str, str]] = {}  # agent_id -> {version: template}

    def register(self, agent_id: str, version: str, template: str) -> None:
        self._prompts.setdefault(agent_id, {})[version] = template

    def get(self, agent_id: str, *, version: str | None = None) -> str:
        versions = self._prompts.get(agent_id, {})
        if not versions:
            from forge_agent.exceptions import PromptNotFoundError

            raise PromptNotFoundError(agent_id)
        if version is None:
            return versions[max(versions.keys())]
        return versions[version]

    def render(
        self,
        agent_id: str,
        variables: dict[str, Any],
        *,
        version: str | None = None,
    ) -> str:
        template = self.get(agent_id, version=version)
        try:
            return template.format(**variables)
        except KeyError as exc:
            from forge_agent.exceptions import PromptVariableError

            raise PromptVariableError(agent_id, str(exc.args[0])) from exc

    def list_versions(self, agent_id: str) -> list[str]:
        return list(self._prompts.get(agent_id, {}).keys())
