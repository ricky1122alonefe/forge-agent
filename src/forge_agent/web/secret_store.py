"""SQLite-backed encrypted storage for LLM API keys (tenant + project scoped)."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

_lock = Lock()
_stores: dict[str, LLMSecretStore] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _master_key(data_root: Path) -> bytes:
    """Load or create a machine-local master key (outside project directories)."""
    key_path = data_root / "secrets" / ".master_key"
    if key_path.is_file():
        return base64.urlsafe_b64decode(key_path.read_bytes())
    raw = os.urandom(32)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(base64.urlsafe_b64encode(raw))
    with contextlib.suppress(OSError):
        key_path.chmod(0o600)
    return raw


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.pbkdf2_hmac(
            "sha256",
            key,
            nonce + counter.to_bytes(4, "big"),
            100_000,
            dklen=32,
        )
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("xor length mismatch")
    return bytes(left[i] ^ right[i] for i in range(len(left)))


def _encrypt(plaintext: str, key: bytes) -> str:
    raw = plaintext.encode("utf-8")
    nonce = os.urandom(16)
    stream = _keystream(key, nonce, len(raw))
    cipher = _xor_bytes(raw, stream)
    return base64.urlsafe_b64encode(nonce + cipher).decode("ascii")


def _decrypt(token: str, key: bytes) -> str:
    blob = base64.urlsafe_b64decode(token.encode("ascii"))
    nonce, cipher = blob[:16], blob[16:]
    stream = _keystream(key, nonce, len(cipher))
    raw = _xor_bytes(cipher, stream)
    return raw.decode("utf-8")


class LLMSecretStore:
    """Persist API keys encrypted in SQLite under the forge-agent data root."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root.expanduser().resolve()
        self.db_path = self.data_root / "secrets" / "llm_keys.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._master = _master_key(self.data_root)
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
            CREATE TABLE IF NOT EXISTS llm_api_keys (
                tenant_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                env_name TEXT NOT NULL,
                ciphertext TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, project_id, env_name)
            );
            """
        )
        self.conn.commit()

    def set_key(
        self,
        tenant_id: str,
        project_id: str,
        env_name: str,
        api_key: str,
    ) -> None:
        env_name = env_name.strip()
        value = api_key.strip()
        if not env_name or not value:
            raise ValueError("env_name and api_key are required")
        ciphertext = _encrypt(value, self._master)
        with _lock:
            self.conn.execute(
                """
                INSERT INTO llm_api_keys (tenant_id, project_id, env_name, ciphertext, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, project_id, env_name) DO UPDATE SET
                    ciphertext = excluded.ciphertext,
                    updated_at = excluded.updated_at
                """,
                (tenant_id, project_id, env_name, ciphertext, _now_iso()),
            )
            self.conn.commit()
        os.environ[env_name] = value

    def get_key(self, tenant_id: str, project_id: str, env_name: str) -> str | None:
        row = self.conn.execute(
            "SELECT ciphertext FROM llm_api_keys WHERE tenant_id = ? AND project_id = ? AND env_name = ?",
            (tenant_id, project_id, env_name.strip()),
        ).fetchone()
        if row is None:
            return None
        try:
            return _decrypt(row["ciphertext"], self._master)
        except (ValueError, UnicodeDecodeError):
            return None

    def delete_key(self, tenant_id: str, project_id: str, env_name: str) -> None:
        with _lock:
            self.conn.execute(
                "DELETE FROM llm_api_keys WHERE tenant_id = ? AND project_id = ? AND env_name = ?",
                (tenant_id, project_id, env_name.strip()),
            )
            self.conn.commit()

    def list_env_names(self, tenant_id: str, project_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT env_name FROM llm_api_keys WHERE tenant_id = ? AND project_id = ?",
            (tenant_id, project_id),
        ).fetchall()
        return [str(r["env_name"]) for r in rows]

    def has_key(self, tenant_id: str, project_id: str, env_name: str | None) -> bool:
        if not env_name:
            return False
        return self.get_key(tenant_id, project_id, env_name) is not None

    def apply_to_environment(self, tenant_id: str, project_id: str) -> None:
        """Load all stored keys for a project into os.environ."""
        rows = self.conn.execute(
            "SELECT env_name, ciphertext FROM llm_api_keys WHERE tenant_id = ? AND project_id = ?",
            (tenant_id, project_id),
        ).fetchall()
        for row in rows:
            try:
                os.environ[row["env_name"]] = _decrypt(row["ciphertext"], self._master)
            except (ValueError, UnicodeDecodeError):
                continue


def get_secret_store(data_root: Path) -> LLMSecretStore:
    root = str(data_root.expanduser().resolve())
    if root not in _stores:
        _stores[root] = LLMSecretStore(data_root)
    return _stores[root]
