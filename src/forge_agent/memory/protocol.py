"""Memory backend protocol for forge-agent.

The memory layer is a generic framework capability. Any agent can store,
retrieve, and query historical records by key, scope, or time. Backends are
pluggable: in-memory for tests/dev, JSON file for simple persistence, SQLite
for production workloads.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    """Pluggable long-term memory backend for agents.

    Implementations must be async-safe and support the same filtering keys
    used by ``BaseAgent`` (agent_id, scope_id, domain, timestamp, etc.).
    """

    async def store(self, key: str, value: dict[str, Any]) -> None:
        """Store a memory record."""
        ...

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        """Fetch a single record by exact key."""
        ...

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        """Query records by arbitrary filters.

        Common filters used by the framework:
            - agent_id: str
            - scope_id: str
            - domain: str
            - start_time / end_time: ISO timestamps
            - limit: int
            - offset: int
        """
        ...

    async def close(self) -> None:
        """Release any underlying resources (no-op for stateless backends)."""
        ...
