"""SQLiteConnection — shared connection management for all SQLite stores.

Extracts the common pattern used by SQLiteReportStore, SQLiteUsageStore,
SQLiteDataStore into a single reusable base class.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_DEFAULT_DB_DIR = Path.home() / ".forge_agent"


class SQLiteConnection:
    """Manages a lazy SQLite connection with WAL mode and busy_timeout.

    Subclasses define their schema by overriding ``_ensure_schema()``.

    Usage::

        class MyStore(SQLiteConnection):
            def _default_db_name(self) -> str:
                return "my_data.db"

            def _ensure_schema(self) -> None:
                self.conn.executescript(\"\"\"
                    CREATE TABLE IF NOT EXISTS my_table (...);
                \"\"\")
                self.conn.commit()
    """

    def __init__(self, db_path: str | Path | None = None, db_name: str = "") -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            name = db_name or self._default_db_name()
            self.db_path = _DEFAULT_DB_DIR / name
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _default_db_name(self) -> str:
        """Override to provide a default database filename."""
        return "forge_data.db"

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection with WAL mode and busy_timeout."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=10,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self) -> None:
        """Override to create tables and indexes."""

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Convenience: execute a single statement."""
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        """Convenience: execute with multiple parameter sets."""
        return self.conn.executemany(sql, params_list)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SQLiteConnection:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
