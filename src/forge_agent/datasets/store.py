"""DatasetStore — persistent storage for datasets.

Two implementations:
- LocalDatasetStore: JSON files on disk (simple, portable)
- SQLiteDatasetStore: SQLite database (queryable, concurrent-safe)

Usage::

    from forge_agent.datasets.store import LocalDatasetStore, SQLiteDatasetStore

    # JSON-based
    store = LocalDatasetStore(Path("./datasets"))
    store.save(dataset)
    ds = store.load("product_examples")

    # SQLite-based
    store = SQLiteDatasetStore(Path("./datasets/datasets.db"))
    store.save(dataset)
    ds = store.load("product_examples")
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Protocol

from forge_agent.datasets import Dataset, DatasetItem

log = logging.getLogger(__name__)


class DatasetStore(Protocol):
    """Protocol for dataset storage backends."""

    def save(self, dataset: Dataset) -> None:
        """Save a dataset (create or update)."""
        ...

    def load(self, name: str) -> Dataset | None:
        """Load a dataset by name. Returns None if not found."""
        ...

    def delete(self, name: str) -> bool:
        """Delete a dataset by name. Returns True if deleted."""
        ...

    def list(self) -> list[str]:
        """List all dataset names."""
        ...

    def exists(self, name: str) -> bool:
        """Check if a dataset exists."""
        ...


class LocalDatasetStore:
    """JSON file-based dataset storage.

    Layout::

        root/
            dataset_name.json
            another_dataset.json
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def save(self, dataset: Dataset) -> None:
        """Save dataset to JSON file."""
        path = self._path_for(dataset.name)
        data = json.dumps(dataset.to_dict(), indent=2, ensure_ascii=False)
        path.write_text(data, encoding="utf-8")
        log.debug("Saved dataset '%s' to %s", dataset.name, path)

    def load(self, name: str) -> Dataset | None:
        """Load dataset from JSON file."""
        path = self._path_for(name)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Dataset.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Failed to load dataset '%s': %s", name, exc)
            return None

    def delete(self, name: str) -> bool:
        """Delete dataset JSON file."""
        path = self._path_for(name)
        if path.is_file():
            path.unlink()
            log.debug("Deleted dataset '%s'", name)
            return True
        return False

    def list(self) -> list[str]:
        """List all dataset names (without .json extension)."""
        return [p.stem for p in self.root.glob("*.json") if p.is_file()]

    def exists(self, name: str) -> bool:
        """Check if dataset file exists."""
        return self._path_for(name).is_file()


class SQLiteDatasetStore:
    """SQLite-based dataset storage.

    Schema::

        datasets (
            name TEXT PRIMARY KEY,
            description TEXT,
            tags TEXT,  -- JSON array
            version TEXT,
            created_at TEXT,
            updated_at TEXT
        )

        dataset_items (
            id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            input TEXT,  -- JSON
            output TEXT,  -- JSON
            metadata TEXT,  -- JSON
            FOREIGN KEY (dataset_name) REFERENCES datasets(name)
        )
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
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
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS datasets (
                name TEXT PRIMARY KEY,
                description TEXT,
                tags TEXT,
                version TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS dataset_items (
                id TEXT PRIMARY KEY,
                dataset_name TEXT NOT NULL,
                input TEXT,
                output TEXT,
                metadata TEXT,
                FOREIGN KEY (dataset_name) REFERENCES datasets(name)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_items_dataset
                ON dataset_items(dataset_name);
        """)
        self.conn.commit()

    def save(self, dataset: Dataset) -> None:
        """Save dataset and all items (upsert)."""
        # Upsert dataset metadata
        self.conn.execute(
            """INSERT INTO datasets (name, description, tags, version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   description=excluded.description,
                   tags=excluded.tags,
                   version=excluded.version,
                   updated_at=excluded.updated_at""",
            (
                dataset.name,
                dataset.description,
                json.dumps(dataset.tags, ensure_ascii=False),
                dataset.version,
                dataset.created_at,
                dataset.updated_at,
            ),
        )

        # Delete old items and insert new ones (simple strategy)
        self.conn.execute("DELETE FROM dataset_items WHERE dataset_name = ?", (dataset.name,))
        for item in dataset.items:
            self.conn.execute(
                """INSERT INTO dataset_items (id, dataset_name, input, output, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    item.id,
                    dataset.name,
                    json.dumps(item.input, ensure_ascii=False),
                    json.dumps(item.output, ensure_ascii=False),
                    json.dumps(item.metadata, ensure_ascii=False),
                ),
            )
        self.conn.commit()
        log.debug("Saved dataset '%s' with %d items", dataset.name, len(dataset.items))

    def load(self, name: str) -> Dataset | None:
        """Load dataset and all items."""
        row = self.conn.execute(
            "SELECT name, description, tags, version, created_at, updated_at FROM datasets WHERE name = ?",
            (name,),
        ).fetchone()
        if not row:
            return None

        tags = json.loads(row[2]) if row[2] else []
        dataset = Dataset(
            name=row[0],
            description=row[1] or "",
            tags=tags,
            version=row[3] or "1.0",
            created_at=row[4],
            updated_at=row[5],
        )

        # Load items
        item_rows = self.conn.execute(
            "SELECT id, input, output, metadata FROM dataset_items WHERE dataset_name = ?",
            (name,),
        ).fetchall()
        for irow in item_rows:
            item = DatasetItem(
                id=irow[0],
                input=json.loads(irow[1]) if irow[1] else None,
                output=json.loads(irow[2]) if irow[2] else None,
                metadata=json.loads(irow[3]) if irow[3] else {},
            )
            dataset.items.append(item)

        return dataset

    def delete(self, name: str) -> bool:
        """Delete dataset and all items."""
        cursor = self.conn.execute("DELETE FROM datasets WHERE name = ?", (name,))
        self.conn.commit()
        if cursor.rowcount > 0:
            log.debug("Deleted dataset '%s'", name)
            return True
        return False

    def list(self) -> list[str]:
        """List all dataset names."""
        rows = self.conn.execute("SELECT name FROM datasets ORDER BY name").fetchall()
        return [row[0] for row in rows]

    def exists(self, name: str) -> bool:
        """Check if dataset exists."""
        row = self.conn.execute("SELECT 1 FROM datasets WHERE name = ?", (name,)).fetchone()
        return row is not None

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
