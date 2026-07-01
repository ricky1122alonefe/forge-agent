"""Tests for forge_agent.memory backends."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from forge_agent.memory import (
    FileMemoryBackend,
    InMemoryMemoryBackend,
    MemoryBackend,
    SQLiteMemoryBackend,
    create_memory_backend,
)


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    return tmp_path / "memory.json"


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "memory.db"


class TestInMemoryMemoryBackend:
    async def test_store_and_retrieve(self) -> None:
        mem = InMemoryMemoryBackend()
        await mem.store("k1", {"agent_id": "a1", "value": 1})
        record = await mem.retrieve("k1")
        assert record is not None
        assert record["agent_id"] == "a1"
        assert record["value"] == 1
        assert "_stored_at" in record

    async def test_retrieve_missing(self) -> None:
        mem = InMemoryMemoryBackend()
        assert await mem.retrieve("missing") is None

    async def test_query_by_agent_id(self) -> None:
        mem = InMemoryMemoryBackend()
        await mem.store("k1", {"agent_id": "a1", "scope_id": "s1"})
        await mem.store("k2", {"agent_id": "a1", "scope_id": "s2"})
        await mem.store("k3", {"agent_id": "a2", "scope_id": "s1"})
        results = await mem.query(agent_id="a1")
        assert len(results) == 2
        assert {r["scope_id"] for r in results} == {"s1", "s2"}

    async def test_query_limit_and_offset(self) -> None:
        mem = InMemoryMemoryBackend()
        for i in range(5):
            await mem.store(
                f"k{i}",
                {
                    "agent_id": "a",
                    "value": i,
                    "timestamp": f"2025-01-0{i + 1}T00:00:00+00:00",
                },
            )
        results = await mem.query(agent_id="a", limit=2, offset=1)
        assert len(results) == 2
        # Descending order by timestamp; offset=1 skips the newest (01-05).
        assert results[0]["timestamp"] == "2025-01-04T00:00:00+00:00"
        assert results[1]["timestamp"] == "2025-01-03T00:00:00+00:00"

    async def test_max_size_eviction(self) -> None:
        mem = InMemoryMemoryBackend(max_size=2)
        await mem.store("k1", {"value": 1})
        await mem.store("k2", {"value": 2})
        await mem.store("k3", {"value": 3})
        assert len(await mem.query()) == 2


class TestFileMemoryBackend:
    async def test_store_persists(self, temp_file: Path) -> None:
        mem = FileMemoryBackend(path=temp_file)
        await mem.store("k1", {"agent_id": "a1", "value": 42})
        await mem.close()

        raw = json.loads(temp_file.read_text(encoding="utf-8"))
        assert "k1" in raw
        assert raw["k1"]["agent_id"] == "a1"

    async def test_load_existing(self, temp_file: Path) -> None:
        temp_file.write_text(
            json.dumps({"k1": {"agent_id": "a1", "value": 42}}, ensure_ascii=False),
            encoding="utf-8",
        )
        mem = FileMemoryBackend(path=temp_file)
        record = await mem.retrieve("k1")
        assert record is not None
        assert record["value"] == 42

    async def test_query_by_scope(self, temp_file: Path) -> None:
        mem = FileMemoryBackend(path=temp_file)
        await mem.store("k1", {"agent_id": "a", "scope_id": "s1"})
        await mem.store("k2", {"agent_id": "a", "scope_id": "s2"})
        results = await mem.query(scope_id="s1")
        assert len(results) == 1
        assert results[0]["scope_id"] == "s1"


class TestSQLiteMemoryBackend:
    async def test_store_and_retrieve(self, temp_db: Path) -> None:
        mem = SQLiteMemoryBackend(path=temp_db)
        await mem.store("k1", {"agent_id": "a1", "scope_id": "s1", "value": 10})
        record = await mem.retrieve("k1")
        assert record is not None
        assert record["agent_id"] == "a1"
        assert record["scope_id"] == "s1"
        assert record["value"] == 10

    async def test_query_time_range(self, temp_db: Path) -> None:
        mem = SQLiteMemoryBackend(path=temp_db)
        for i in range(3):
            await mem.store(
                f"k{i}",
                {
                    "agent_id": "a",
                    "scope_id": f"s{i}",
                    "timestamp": f"2025-01-0{i + 1}T00:00:00+00:00",
                },
            )
        results = await mem.query(
            agent_id="a",
            start_time="2025-01-02T00:00:00+00:00",
            end_time="2025-01-03T00:00:00+00:00",
        )
        assert len(results) == 2
        assert {r["scope_id"] for r in results} == {"s1", "s2"}

    async def test_store_overwrites(self, temp_db: Path) -> None:
        mem = SQLiteMemoryBackend(path=temp_db)
        await mem.store("k1", {"value": 1})
        await mem.store("k1", {"value": 2})
        record = await mem.retrieve("k1")
        assert record is not None
        assert record["value"] == 2

    async def test_schema_created(self, temp_db: Path) -> None:
        mem = SQLiteMemoryBackend(path=temp_db)
        await mem.close()
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_records'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    async def test_in_memory(self) -> None:
        mem = SQLiteMemoryBackend(path=":memory:")
        await mem.store("k1", {"value": 1})
        assert await mem.retrieve("k1") is not None


class TestCreateMemoryBackend:
    def test_default_is_in_memory(self) -> None:
        backend = create_memory_backend()
        assert isinstance(backend, InMemoryMemoryBackend)

    def test_file_backend(self, tmp_path: Path) -> None:
        path = tmp_path / "memory.json"
        backend = create_memory_backend({"backend": "file", "path": str(path)})
        assert isinstance(backend, FileMemoryBackend)
        assert backend._path == path

    def test_sqlite_backend(self, tmp_path: Path) -> None:
        path = tmp_path / "memory.db"
        backend = create_memory_backend({"backend": "sqlite", "path": str(path)})
        assert isinstance(backend, SQLiteMemoryBackend)

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError):
            create_memory_backend({"backend": "redis"})


class TestProtocolCompliance:
    def test_all_backends_comply(self, temp_file: Path, temp_db: Path) -> None:
        backends: list[MemoryBackend] = [
            InMemoryMemoryBackend(),
            FileMemoryBackend(path=temp_file),
            SQLiteMemoryBackend(path=temp_db),
        ]
        for backend in backends:
            assert isinstance(backend, MemoryBackend)
