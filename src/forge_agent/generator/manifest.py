"""Manifest — project-level registry of generated Agents.

The manifest is the **source of truth** for what generated agents exist in
this project, which version is active, and where the code lives on disk.

It MUST be committed to git. The actual .py files in generated_agents/ are
git-ignored; the manifest tells you what should be there.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class AgentVersionMeta:
    """Metadata for a single version of a generated agent."""

    version: str                        # "v1", "v2", ...
    created_at: str                     # ISO8601
    created_by: str                     # user / system
    requirement: str                    # original natural language
    llm_provider: str | None = None
    llm_model: str | None = None
    validation_status: str = "unknown"  # "passed" | "failed" | "unknown"
    validation_errors: list[str] = field(default_factory=list)
    smoke_test_status: str = "unknown"
    smoke_test_error: str | None = None
    code_hash: str | None = None
    code_path: str | None = None        # relative to project root
    supersedes: str | None = None       # previous version replaced
    deprecated: bool = False
    deprecated_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentVersionMeta":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentManifestEntry:
    """One entry in the manifest — a single generated agent across versions."""

    agent_id: str
    created_at: str
    active_version: str                 # e.g. "v3"
    versions: list[AgentVersionMeta] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "active_version": self.active_version,
            "versions": [v.to_dict() for v in self.versions],
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentManifestEntry":
        versions = [AgentVersionMeta.from_dict(v) for v in d.get("versions", [])]
        return cls(
            agent_id=d["agent_id"],
            created_at=d.get("created_at", _now()),
            active_version=d.get("active_version", "v1"),
            versions=versions,
            description=d.get("description", ""),
        )

    def get_version(self, version: str) -> AgentVersionMeta | None:
        for v in self.versions:
            if v.version == version:
                return v
        return None

    def get_active(self) -> AgentVersionMeta | None:
        return self.get_version(self.active_version)


@dataclass
class Manifest:
    """Project-level manifest of all generated agents."""

    version: int = 2
    project: str = ""
    updated_at: str = field(default_factory=lambda: _now())
    agents: dict[str, AgentManifestEntry] = field(default_factory=dict)
    archive: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "project": self.project,
            "updated_at": self.updated_at,
            "agents": {aid: e.to_dict() for aid, e in self.agents.items()},
            "archive": self.archive,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Manifest":
        return cls(
            version=int(d.get("version", 2)),
            project=str(d.get("project", "")),
            updated_at=str(d.get("updated_at", _now())),
            agents={aid: AgentManifestEntry.from_dict(e) for aid, e in (d.get("agents") or {}).items()},
            archive=list(d.get("archive", [])),
        )

    # ------------------------------------------------------------------ IO

    def save(self, path: Path | str) -> None:
        """Atomically write the manifest to disk (POSIX rename)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = _now()
        data = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        # Atomic write: temp file in same dir, then rename
        fd, tmp = tempfile.mkstemp(
            prefix=".MANIFEST.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: Path | str) -> "Manifest":
        path = Path(path)
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except json.JSONDecodeError as exc:
            log.warning("Manifest at %s is invalid JSON: %s", path, exc)
            return cls()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
