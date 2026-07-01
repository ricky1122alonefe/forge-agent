"""Memory backend implementations.

Provides three generic backends:
- InMemoryMemoryBackend: fast, ephemeral, for tests/dev
- FileMemoryBackend: JSON-file persistence, for simple single-node setups
- SQLiteMemoryBackend: durable, indexed, for production use

All backends implement ``MemoryBackend`` and are interchangeable for agents.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forge_agent.memory.protocol import MemoryBackend


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryMemoryBackend:
    """In-process memory backend. Fast but ephemeral."""

    def __init__(self, *, max_size: int = 10_000) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._max_size = max_size

    async def store(self, key: str, value: dict[str, Any]) -> None:
        if len(self._data) >= self._max_size and key not in self._data:
            # Simple eviction: drop the oldest key (arbitrary but deterministic).
            oldest = next(iter(self._data))
            del self._data[oldest]
        self._data[key] = {**value, "_stored_at": _now_iso()}

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        results = list(self._data.values())
        return _apply_filters(results, filters)

    async def close(self) -> None:
        self._data.clear()


class FileMemoryBackend:
    """JSON-file persisted memory backend."""

    def __init__(self, *, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    async def store(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = {**value, "_stored_at": _now_iso()}
        self._save()

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        return _apply_filters(list(self._data.values()), filters)

    async def close(self) -> None:
        self._save()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class SQLiteMemoryBackend:
    """SQLite-backed memory backend. Durable and indexed."""

    def __init__(self, *, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    async def store(self, key: str, value: dict[str, Any]) -> None:
        agent_id = str(value.get("agent_id", ""))
        scope_id = str(value.get("scope_id", ""))
        domain = str(value.get("domain", ""))
        timestamp = str(value.get("timestamp", _now_iso()))
        payload = {
            k: v
            for k, v in value.items()
            if k not in {"agent_id", "scope_id", "domain", "timestamp"}
        }
        payload_json = json.dumps(payload, ensure_ascii=False)

        self._conn.execute(
            """
            INSERT INTO memory_records (key, agent_id, scope_id, domain, timestamp, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                agent_id=excluded.agent_id,
                scope_id=excluded.scope_id,
                domain=excluded.domain,
                timestamp=excluded.timestamp,
                payload=excluded.payload,
                updated_at=datetime('now')
            """,
            (key, agent_id, scope_id, domain, timestamp, payload_json),
        )
        self._conn.commit()

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT key, agent_id, scope_id, domain, timestamp, payload FROM memory_records WHERE key = ?",
            (key,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        limit: int = int(filters.pop("limit", 100))
        offset: int = int(filters.pop("offset", 0))
        start_time = filters.pop("start_time", None)
        end_time = filters.pop("end_time", None)

        for k, v in filters.items():
            if v is None:
                continue
            conditions.append(f"{k} = ?")
            params.append(str(v))

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(str(start_time))
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(str(end_time))

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        rows = self._conn.execute(
            f"""SELECT key, agent_id, scope_id, domain, timestamp, payload
                  FROM memory_records
                 WHERE {where}
                 ORDER BY timestamp DESC
                 LIMIT ? OFFSET ?""",
            params,
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                key TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL DEFAULT '',
                scope_id TEXT NOT NULL DEFAULT '',
                domain TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_records(agent_id);
            CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_records(scope_id);
            CREATE INDEX IF NOT EXISTS idx_memory_domain ON memory_records(domain);
            CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_records(timestamp DESC);
            """
        )
        self._conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if row["payload"]:
            with contextlib.suppress(json.JSONDecodeError):
                payload = json.loads(row["payload"])
        return {
            "key": row["key"],
            "agent_id": row["agent_id"],
            "scope_id": row["scope_id"],
            "domain": row["domain"],
            "timestamp": row["timestamp"],
            **payload,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_filters(records: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply common filters to an in-memory list of records."""
    limit: int = int(filters.pop("limit", 100))
    offset: int = int(filters.pop("offset", 0))
    start_time = filters.pop("start_time", None)
    end_time = filters.pop("end_time", None)

    results = records
    for k, v in filters.items():
        if v is None:
            continue
        results = [r for r in results if str(r.get(k, "")) == str(v)]

    if start_time or end_time:
        results = [
            r
            for r in results
            if (not start_time or str(r.get("timestamp", "")) >= str(start_time))
            and (not end_time or str(r.get("timestamp", "")) <= str(end_time))
        ]

    # Sort by timestamp descending when available, otherwise stable order.
    results = sorted(
        results,
        key=lambda r: str(r.get("timestamp", "")),
        reverse=True,
    )
    return results[offset : offset + limit]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_memory_backend(config: dict[str, Any] | None = None) -> MemoryBackend:
    """Create a memory backend from configuration.

    Config keys:
        - backend: "memory" | "file" | "sqlite" (default "memory")
        - path: file path for "file" / "sqlite" backends
        - max_size: optional size limit for in-memory backend

    Examples:
        create_memory_backend()                         # InMemoryMemoryBackend
        create_memory_backend({"backend": "file", "path": "memory.json"})
        create_memory_backend({"backend": "sqlite", "path": "memory.db"})
    """
    cfg = dict(config or {})
    backend_type = cfg.get("backend", "memory")

    if backend_type == "memory":
        return InMemoryMemoryBackend(max_size=cfg.get("max_size", 10_000))
    if backend_type == "file":
        path = cfg.get("path", "memory.json")
        return FileMemoryBackend(path=path)
    if backend_type == "sqlite":
        path = cfg.get("path", "memory.db")
        return SQLiteMemoryBackend(path=path)

    raise ValueError(f"Unknown memory backend: {backend_type!r}")
