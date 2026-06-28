"""ForgeStore — unified time-series record store for all agent types.

A single store that any agent can use to persist structured data.
Replaces the need for each agent type to have its own SQLite store.

Schema:
    forge_records (
        id, agent_id, category, timestamp, data[JSON],
        source, checksum, tags, created_at
    )

- agent_id: which agent produced this record
- category: data category (e.g. "scraped", "metric", "analysis", "generated")
- data: JSON payload — flexible schema per record
- source: optional origin URL or identifier
- checksum: optional dedup hash
- tags: optional comma-separated tags for filtering
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from forge_agent.storage.base import SQLiteConnection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_checksum(data: dict[str, Any]) -> str:
    """Compute MD5 checksum for dedup."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


@dataclass
class Record:
    """A single data record stored by any agent."""

    agent_id: str
    data: dict[str, Any]
    category: str = ""
    timestamp: str = ""
    source: str = ""
    checksum: str = ""
    tags: list[str] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "category": self.category,
            "timestamp": self.timestamp,
            "data": self.data,
            "source": self.source,
            "checksum": self.checksum,
            "tags": self.tags,
        }

    @classmethod
    def from_row(cls, row: tuple[Any, ...]) -> Record:
        data: dict[str, Any] = {}
        if row[4]:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                data = json.loads(row[4])
        tags: list[str] = []
        if row[7]:
            tags = [t.strip() for t in row[7].split(",") if t.strip()]
        return cls(
            id=row[0],
            agent_id=row[1],
            category=row[2] or "",
            timestamp=row[3] or "",
            data=data,
            source=row[5] or "",
            checksum=row[6] or "",
            tags=tags,
        )


class ForgeStore(SQLiteConnection):
    """Unified time-series record store for all agent types.

    Usage::

        store = ForgeStore()

        # Scraper stores scraped data
        store.insert(
            "weather.beijing",
            {"temp": 25, "humidity": 60},
            category="scraped",
            source="https://wttr.in/Beijing",
        )

        # Monitor stores metrics
        store.insert(
            "server.monitor", {"cpu": 85, "memory": 72}, category="metric", tags=["production", "web"]
        )

        # Analyzer stores analysis results
        store.insert("news.analyzer", {"sentiment": "positive", "score": 0.85}, category="analysis")

        # Query
        records = store.query(agent_id="weather.beijing", limit=100)

        # Time-series for a specific field
        series = store.get_time_series("weather.beijing", "temp")

        # Summary
        stats = store.summary()
    """

    def _default_db_name(self) -> str:
        return "forge_data.db"

    def _ensure_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS forge_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL,
                source TEXT DEFAULT '',
                checksum TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_records_agent_ts
                ON forge_records(agent_id, timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_records_category
                ON forge_records(category);

            CREATE INDEX IF NOT EXISTS idx_records_checksum
                ON forge_records(checksum);

            CREATE INDEX IF NOT EXISTS idx_records_tags
                ON forge_records(tags);
        """)
        self.conn.commit()

    # ── Insert ──────────────────────────────────────────────

    def insert(
        self,
        agent_id: str,
        data: dict[str, Any],
        *,
        category: str = "",
        source: str = "",
        checksum: str = "",
        tags: list[str] | None = None,
        timestamp: str = "",
        dedup: bool = False,
    ) -> Record:
        """Insert a record. Returns the created Record.

        Args:
            agent_id: Which agent produced this data.
            data: The structured data payload.
            category: Data category (scraped/metric/analysis/generated).
            source: Optional origin URL or identifier.
            checksum: Optional dedup hash. Auto-computed if dedup=True.
            tags: Optional tags for filtering.
            timestamp: Optional timestamp. Auto-generated if empty.
            dedup: If True, auto-compute checksum and skip duplicates.

        Returns:
            The inserted Record (or existing one if duplicate).
        """
        ts = timestamp or _now_iso()
        tag_str = ",".join(tags) if tags else ""

        if dedup and not checksum:
            checksum = compute_checksum(data)

        # Check for duplicates
        if checksum and self._exists(checksum):
            existing = self._get_by_checksum(checksum)
            if existing:
                return existing

        data_json = json.dumps(data, ensure_ascii=False)

        cursor = self.conn.execute(
            """INSERT INTO forge_records
               (agent_id, category, timestamp, data, source, checksum, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, category, ts, data_json, source, checksum, tag_str),
        )
        self.conn.commit()

        return Record(
            id=cursor.lastrowid,
            agent_id=agent_id,
            category=category,
            timestamp=ts,
            data=data,
            source=source,
            checksum=checksum,
            tags=tags or [],
        )

    def insert_batch(
        self,
        records: list[Record],
        *,
        dedup: bool = False,
    ) -> list[Record]:
        """Insert multiple records in a single transaction."""
        inserted: list[Record] = []
        for rec in records:
            if dedup:
                cs = rec.checksum or compute_checksum(rec.data)
                if self._exists(cs):
                    continue
                rec.checksum = cs

            data_json = json.dumps(rec.data, ensure_ascii=False)
            tag_str = ",".join(rec.tags) if rec.tags else ""
            ts = rec.timestamp or _now_iso()

            cursor = self.conn.execute(
                """INSERT INTO forge_records
                   (agent_id, category, timestamp, data, source, checksum, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rec.agent_id, rec.category, ts, data_json, rec.source, rec.checksum, tag_str),
            )
            rec.id = cursor.lastrowid
            rec.timestamp = ts
            inserted.append(rec)

        self.conn.commit()
        return inserted

    # ── Query ───────────────────────────────────────────────

    def query(
        self,
        *,
        agent_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Record]:
        """Query records with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if tag:
            conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        cursor = self.conn.execute(
            f"""SELECT id, agent_id, category, timestamp, data,
                       source, checksum, tags
                FROM forge_records
                WHERE {where}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?""",
            params,
        )
        return [Record.from_row(row) for row in cursor.fetchall()]

    def get_latest(self, agent_id: str, limit: int = 10) -> list[Record]:
        """Get the most recent records for an agent."""
        return self.query(agent_id=agent_id, limit=limit)

    def get_time_series(
        self,
        agent_id: str,
        field_name: str,
        *,
        category: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get time-series data for a specific field.

        Returns list of {"timestamp": "...", "value": ...}
        """
        records = self.query(
            agent_id=agent_id,
            category=category,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        series: list[dict[str, Any]] = []
        for rec in records:
            value = rec.data.get(field_name)
            if value is not None:
                series.append({"timestamp": rec.timestamp, "value": value})
        return series

    # ── Aggregation ─────────────────────────────────────────

    def summary(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get summary statistics."""
        if agent_id:
            cursor = self.conn.execute(
                """SELECT
                       COUNT(*) as total,
                       MIN(timestamp) as first_record,
                       MAX(timestamp) as last_record
                   FROM forge_records
                   WHERE agent_id = ?""",
                (agent_id,),
            )
            row = cursor.fetchone()
            # Category breakdown
            cat_cursor = self.conn.execute(
                """SELECT category, COUNT(*) as cnt
                   FROM forge_records
                   WHERE agent_id = ?
                   GROUP BY category
                   ORDER BY cnt DESC""",
                (agent_id,),
            )
            return {
                "agent_id": agent_id,
                "total_records": row[0],
                "first_record": row[1],
                "last_record": row[2],
                "by_category": {r[0]: r[1] for r in cat_cursor.fetchall()},
            }
        else:
            cursor = self.conn.execute(
                """SELECT
                       COUNT(*) as total,
                       MIN(timestamp) as first_record,
                       MAX(timestamp) as last_record,
                       COUNT(DISTINCT agent_id) as unique_agents
                   FROM forge_records"""
            )
            row = cursor.fetchone()
            # Agent breakdown
            agent_cursor = self.conn.execute(
                """SELECT agent_id, COUNT(*) as cnt
                   FROM forge_records
                   GROUP BY agent_id
                   ORDER BY cnt DESC
                   LIMIT 20"""
            )
            # Category breakdown
            cat_cursor = self.conn.execute(
                """SELECT category, COUNT(*) as cnt
                   FROM forge_records
                   GROUP BY category
                   ORDER BY cnt DESC"""
            )
            return {
                "total_records": row[0],
                "first_record": row[1],
                "last_record": row[2],
                "unique_agents": row[3],
                "by_agent": {r[0]: r[1] for r in agent_cursor.fetchall()},
                "by_category": {r[0]: r[1] for r in cat_cursor.fetchall()},
            }

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents with record counts."""
        cursor = self.conn.execute(
            """SELECT agent_id, COUNT(*) as cnt, MAX(timestamp) as last_ts
               FROM forge_records
               GROUP BY agent_id
               ORDER BY last_ts DESC"""
        )
        return [
            {"agent_id": row[0], "record_count": row[1], "last_record": row[2]}
            for row in cursor.fetchall()
        ]

    # ── Delete ──────────────────────────────────────────────

    def delete(
        self,
        agent_id: str,
        *,
        before: str | None = None,
        category: str | None = None,
    ) -> int:
        """Delete records for an agent. Returns count of deleted rows."""
        conditions = ["agent_id = ?"]
        params: list[Any] = [agent_id]
        if before:
            conditions.append("timestamp < ?")
            params.append(before)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = " AND ".join(conditions)
        cursor = self.conn.execute(
            f"DELETE FROM forge_records WHERE {where}",
            params,
        )
        self.conn.commit()
        return cursor.rowcount

    # ── Internal ────────────────────────────────────────────

    def _exists(self, checksum: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM forge_records WHERE checksum = ? LIMIT 1",
            (checksum,),
        )
        return cursor.fetchone() is not None

    def _get_by_checksum(self, checksum: str) -> Record | None:
        cursor = self.conn.execute(
            """SELECT id, agent_id, category, timestamp, data,
                      source, checksum, tags
               FROM forge_records WHERE checksum = ? LIMIT 1""",
            (checksum,),
        )
        row = cursor.fetchone()
        return Record.from_row(row) if row else None
