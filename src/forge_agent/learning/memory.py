"""Long-term memory store.

The InMemoryStore in core.capabilities is fine for short-term & single-node.
For long-term & multi-node, use a vector store / Redis / SQLite.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LongTermStoreProtocol(Protocol):
    async def store(self, key: str, value: dict[str, Any]) -> None: ...
    async def retrieve(self, key: str) -> dict[str, Any] | None: ...
    async def query(self, **filters: Any) -> list[dict[str, Any]]: ...


class InMemoryLongTermStore:
    """In-process long-term store with simple JSON-file persistence."""

    def __init__(self, *, persist_path: str | Path | None = None) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.is_file():
            try:
                self._data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    async def store(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = {**value, "_stored_at": datetime.now(timezone.utc).isoformat()}
        if self._persist_path:
            self._persist_path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        items = list(self._data.values())
        for k, v in filters.items():
            items = [it for it in items if it.get(k) == v]
        return items
