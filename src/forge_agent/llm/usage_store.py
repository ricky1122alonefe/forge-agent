"""SQLiteUsageStore — persistent storage for token usage records.

Schema:
    token_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        tokens_in INTEGER NOT NULL,
        tokens_out INTEGER NOT NULL,
        cost_usd REAL NOT NULL,
        timestamp TEXT NOT NULL,
        agent_id TEXT,
        session_id TEXT,
        metadata TEXT  -- JSON
    )
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Default DB location
_DEFAULT_DB_DIR = Path.home() / ".forge_agent"
_ENV_DB_PATH = "FORGE_AGENT_DB_PATH"


def _default_db_path() -> Path:
    env = os.environ.get(_ENV_DB_PATH)
    if env:
        return Path(env)
    return _DEFAULT_DB_DIR / "token_usage.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TokenUsage:
    """A single LLM call's token consumption record."""

    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    timestamp: str
    agent_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TokenUsage":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


class SQLiteUsageStore:
    """SQLite-backed persistent store for token usage records."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=10,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _ensure_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                timestamp TEXT NOT NULL,
                agent_id TEXT,
                session_id TEXT,
                metadata TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_token_usage_agent_id
                ON token_usage(agent_id);
            CREATE INDEX IF NOT EXISTS idx_token_usage_session_id
                ON token_usage(session_id);
            CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp
                ON token_usage(timestamp);
            CREATE INDEX IF NOT EXISTS idx_token_usage_provider
                ON token_usage(provider);
        """)
        self.conn.commit()

    def insert(self, usage: TokenUsage) -> TokenUsage:
        """Insert a record and return it with the assigned id."""
        meta_json = json.dumps(usage.metadata, ensure_ascii=False) if usage.metadata else None
        cursor = self.conn.execute(
            """INSERT INTO token_usage
               (provider, model, tokens_in, tokens_out, cost_usd,
                timestamp, agent_id, session_id, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                usage.provider,
                usage.model,
                usage.tokens_in,
                usage.tokens_out,
                usage.cost_usd,
                usage.timestamp,
                usage.agent_id,
                usage.session_id,
                meta_json,
            ),
        )
        self.conn.commit()
        usage.id = cursor.lastrowid
        return usage

    def query(
        self,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        provider: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[TokenUsage]:
        """Query records with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if provider is not None:
            conditions.append("provider = ?")
            params.append(provider)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = f"""SELECT id, provider, model, tokens_in, tokens_out, cost_usd,
                         timestamp, agent_id, session_id, metadata
                  FROM token_usage
                  {where}
                  ORDER BY timestamp DESC
                  LIMIT ?"""
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_usage(row) for row in rows]

    def summary(
        self,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate statistics over matching records."""
        conditions: list[str] = []
        params: list[Any] = []

        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        # Overall totals
        sql = f"""SELECT
                      COUNT(*) as call_count,
                      COALESCE(SUM(tokens_in), 0) as total_tokens_in,
                      COALESCE(SUM(tokens_out), 0) as total_tokens_out,
                      COALESCE(SUM(cost_usd), 0.0) as total_cost_usd
                  FROM token_usage {where}"""
        row = self.conn.execute(sql, params).fetchone()
        result: dict[str, Any] = {
            "call_count": row[0],
            "total_tokens_in": row[1],
            "total_tokens_out": row[2],
            "total_tokens": row[1] + row[2],
            "total_cost_usd": round(row[3], 6),
        }

        # Grouped breakdown
        if group_by and group_by in ("provider", "model", "agent_id", "session_id"):
            col = group_by
            group_sql = f"""SELECT
                                {col},
                                COUNT(*) as call_count,
                                COALESCE(SUM(tokens_in), 0) as tokens_in,
                                COALESCE(SUM(tokens_out), 0) as tokens_out,
                                COALESCE(SUM(cost_usd), 0.0) as cost_usd
                            FROM token_usage {where}
                            GROUP BY {col}
                            ORDER BY cost_usd DESC"""
            rows = self.conn.execute(group_sql, params).fetchall()
            result["by_" + group_by] = {
                (r[0] or "unknown"): {
                    "call_count": r[1],
                    "tokens_in": r[2],
                    "tokens_out": r[3],
                    "total_tokens": r[2] + r[3],
                    "cost_usd": round(r[4], 6),
                }
                for r in rows
            }

        return result

    def reset(self) -> int:
        """Delete all records. Returns the number of deleted rows."""
        count = self.conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]
        self.conn.execute("DELETE FROM token_usage")
        self.conn.commit()
        return count

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_usage(row: tuple) -> TokenUsage:
        meta: dict[str, Any] = {}
        if row[9]:
            try:
                meta = json.loads(row[9])
            except (json.JSONDecodeError, TypeError):
                pass
        return TokenUsage(
            id=row[0],
            provider=row[1],
            model=row[2],
            tokens_in=row[3],
            tokens_out=row[4],
            cost_usd=row[5],
            timestamp=row[6],
            agent_id=row[7],
            session_id=row[8],
            metadata=meta,
        )
