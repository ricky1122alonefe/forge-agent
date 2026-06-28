"""SQLiteDataStore — backward-compatible wrapper around ForgeStore.

This module is kept for backward compatibility. New code should use
``forge_agent.storage.ForgeStore`` directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_agent.storage.store import ForgeStore, Record


class ScrapedRecord:
    """Backward-compatible scraped record (delegates to ForgeStore)."""

    def __init__(
        self,
        agent_id: str,
        timestamp: str,
        data: dict[str, Any],
        url: str = "",
        checksum: str = "",
    ) -> None:
        self.agent_id = agent_id
        self.timestamp = timestamp
        self.data = data
        self.url = url
        self.checksum = checksum

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "url": self.url,
            "checksum": self.checksum,
        }

    @classmethod
    def from_record(cls, rec: Record) -> ScrapedRecord:
        return cls(
            agent_id=rec.agent_id,
            timestamp=rec.timestamp,
            data=rec.data,
            url=rec.source,
            checksum=rec.checksum,
        )


class SQLiteDataStore:
    """Backward-compatible wrapper around ForgeStore for scraper data.

    New code should use ``ForgeStore`` directly with ``category="scraped"``.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._store = ForgeStore(db_path=db_path)

    @property
    def conn(self):
        return self._store.conn

    @property
    def db_path(self) -> Path:
        return self._store.db_path

    def insert(self, record: ScrapedRecord) -> int:
        """Insert a scraped record. Returns the row ID (-1 if duplicate)."""
        rec = Record(
            agent_id=record.agent_id,
            data=record.data,
            category="scraped",
            timestamp=record.timestamp,
            source=record.url,
            checksum=record.checksum,
        )
        result = self._store.insert(
            rec.agent_id,
            rec.data,
            category=rec.category,
            source=rec.source,
            checksum=rec.checksum,
            timestamp=rec.timestamp,
            dedup=bool(rec.checksum),
        )
        if result.id is None:
            return -1
        return result.id or 0

    def query(
        self,
        agent_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScrapedRecord]:
        records = self._store.query(
            agent_id=agent_id,
            category="scraped",
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        return [ScrapedRecord.from_record(r) for r in records]

    def get_latest(self, agent_id: str, limit: int = 10) -> list[ScrapedRecord]:
        return self.query(agent_id=agent_id, limit=limit)

    def get_time_series(
        self,
        agent_id: str,
        field_name: str,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._store.get_time_series(
            agent_id,
            field_name,
            category="scraped",
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def summary(self, agent_id: str | None = None) -> dict[str, Any]:
        return self._store.summary(agent_id)

    def delete(self, agent_id: str, before: str | None = None) -> int:
        return self._store.delete(agent_id, before=before, category="scraped")

    def close(self) -> None:
        self._store.close()
