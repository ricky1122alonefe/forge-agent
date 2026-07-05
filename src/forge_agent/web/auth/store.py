"""SQLite-backed user and session store for web auth."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    username: str
    tenant_id: str
    password_salt: str
    password_hash: str
    created_at: str


class AuthStore:
    """Persist users and sessions under the forge-agent data root."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root.expanduser().resolve()
        self.db_path = self.data_root / "auth" / "users.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            """
        )
        self.conn.commit()

    def get_user_by_username(self, username: str) -> UserRecord | None:
        row = self.conn.execute(
            "SELECT user_id, username, tenant_id, password_salt, password_hash, created_at "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        row = self.conn.execute(
            "SELECT user_id, username, tenant_id, password_salt, password_hash, created_at "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return self._row_to_user(row) if row else None

    def create_user(
        self,
        *,
        username: str,
        tenant_id: str,
        password_salt: str,
        password_hash: str,
    ) -> UserRecord:
        user_id = uuid.uuid4().hex
        created_at = _now_iso()
        try:
            self.conn.execute(
                "INSERT INTO users (user_id, username, tenant_id, password_salt, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, tenant_id, password_salt, password_hash, created_at),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("username or tenant already exists") from exc
        return UserRecord(
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            password_salt=password_salt,
            password_hash=password_hash,
            created_at=created_at,
        )

    def create_session(self, user_id: str, *, ttl_hours: int) -> str:
        session_id = uuid.uuid4().hex
        created_at = _now_iso()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
        self.conn.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, expires_at, created_at),
        )
        self.conn.commit()
        return session_id

    def delete_session(self, session_id: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()

    def get_user_for_session(self, session_id: str) -> UserRecord | None:
        row = self.conn.execute(
            """
            SELECT u.user_id, u.username, u.tenant_id, u.password_salt, u.password_hash, u.created_at
            FROM sessions s
            JOIN users u ON u.user_id = s.user_id
            WHERE s.session_id = ? AND s.expires_at > ?
            """,
            (session_id, _now_iso()),
        ).fetchone()
        return self._row_to_user(row) if row else None

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            user_id=row["user_id"],
            username=row["username"],
            tenant_id=row["tenant_id"],
            password_salt=row["password_salt"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
        )
