"""Memory framework for forge-agent.

A generic, pluggable memory layer. Use it to store, retrieve, and query
agent execution history across runs.

Examples:
    from forge_agent.memory import create_memory_backend

    # In-memory (default, dev/tests)
    mem = create_memory_backend()

    # File-backed
    mem = create_memory_backend({"backend": "file", "path": "memory.json"})

    # SQLite-backed
    mem = create_memory_backend({"backend": "sqlite", "path": "memory.db"})

    await mem.store("run_1", {"agent_id": "a", "scope_id": "s", "value": 42})
    record = await mem.retrieve("run_1")
    records = await mem.query(agent_id="a", limit=10)
"""

from __future__ import annotations

from forge_agent.memory.backends import (
    FileMemoryBackend,
    InMemoryMemoryBackend,
    SQLiteMemoryBackend,
    create_memory_backend,
)
from forge_agent.memory.protocol import MemoryBackend

__all__ = [
    "FileMemoryBackend",
    "InMemoryMemoryBackend",
    "MemoryBackend",
    "SQLiteMemoryBackend",
    "create_memory_backend",
]
