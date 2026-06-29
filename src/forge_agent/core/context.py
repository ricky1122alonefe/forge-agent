"""Agent runtime context.

Passed to every Agent.run() and propagated through the Pipeline.
Domain-agnostic on purpose; business data goes in `payload`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "run") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class AgentContext:
    """Runtime context for an Agent invocation.

    Attributes:
        run_id:       Unique id of this pipeline run.
        scope_id:     Domain-specific id (e.g. fixture_id, ticker).
        scope_name:   Human-readable label.
        domain:       Business domain tag.
        payload:      Domain data (prediction row, market snapshot, etc.).
        config:       Per-run config overrides.
        parent_run_id: Parent pipeline run id (for nested agents).
        metadata:     Free-form additional context.
    """

    scope_id: str
    scope_name: str = ""
    domain: str = "generic"
    payload: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: _new_id("run"))
    parent_run_id: str = ""
    timestamp: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scope_id": self.scope_id,
            "scope_name": self.scope_name,
            "domain": self.domain,
            "payload": self.payload,
            "config": self.config,
            "parent_run_id": self.parent_run_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def child(self, scope_id: str | None = None) -> AgentContext:
        """Create a child context (for nested Agent calls)."""
        return AgentContext(
            scope_id=scope_id or self.scope_id,
            scope_name=self.scope_name,
            domain=self.domain,
            payload=dict(self.payload),
            config=dict(self.config),
            parent_run_id=self.run_id,
            metadata=dict(self.metadata),
        )
