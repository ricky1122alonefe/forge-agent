"""Web UI authentication configuration (P2.3/P2.4)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class WebAuthConfig:
    """Session-based auth for the self-hosted web UI."""

    enabled: bool = False
    session_secret: str = ""
    session_ttl_hours: int = 168
    cookie_name: str = "forge_session"

    @classmethod
    def from_env(cls) -> WebAuthConfig:
        enabled = os.environ.get("FORGE_AGENT_WEB_AUTH", "").lower() in ("1", "true", "yes")
        secret = os.environ.get("FORGE_AGENT_SESSION_SECRET", "").strip()
        ttl_raw = os.environ.get("FORGE_AGENT_SESSION_TTL_HOURS", "168").strip()
        try:
            ttl = max(1, int(ttl_raw))
        except ValueError:
            ttl = 168
        return cls(
            enabled=enabled,
            session_secret=secret or secrets.token_hex(32),
            session_ttl_hours=ttl,
        )
