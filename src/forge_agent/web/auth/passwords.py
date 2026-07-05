"""Password hashing helpers (stdlib only)."""

from __future__ import annotations

import hashlib
import secrets


def hash_password(password: str, *, salt: str | None = None) -> tuple[str, str]:
    """Return (salt, password_hash) using PBKDF2-HMAC-SHA256."""
    if not password:
        raise ValueError("password is required")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return salt, digest.hex()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    _, candidate = hash_password(password, salt=salt)
    return secrets.compare_digest(candidate, password_hash)
