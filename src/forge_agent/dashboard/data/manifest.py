"""Read MANIFEST.json and expose agent/version data for the dashboard."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VersionInfo:
    """Metadata for a single version of a generated agent."""

    version: str
    created_at: str
    created_by: str
    requirement: str
    validation_status: str
    code_hash: str
    code_path: str
    llm_provider: str = ""
    llm_model: str = ""
    smoke_test_status: str = "unknown"
    deprecated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentInfo:
    """Summary info for a single generated agent."""

    agent_id: str
    created_at: str
    active_version: str
    versions: list[VersionInfo] = field(default_factory=list)
    description: str = ""
    agent_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "active_version": self.active_version,
            "versions": [v.to_dict() for v in self.versions],
            "description": self.description,
            "agent_type": self.agent_type,
        }

    @property
    def version_count(self) -> int:
        return len(self.versions)

    @property
    def active_version_info(self) -> VersionInfo | None:
        for v in self.versions:
            if v.version == self.active_version:
                return v
        return None


def load_manifest(project_root: Path) -> dict[str, AgentInfo]:
    """Load MANIFEST.json from a project, return {agent_id: AgentInfo}.

    Looks in ``<project_root>/generated_agents/MANIFEST.json``.
    Returns empty dict if the file doesn't exist.
    """
    manifest_path = project_root / "generated_agents" / "MANIFEST.json"
    if not manifest_path.exists():
        return {}

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    agents: dict[str, AgentInfo] = {}
    for agent_id, entry in data.get("agents", {}).items():
        versions = [
            VersionInfo(
                version=v.get("version", ""),
                created_at=v.get("created_at", ""),
                created_by=v.get("created_by", ""),
                requirement=v.get("requirement", ""),
                validation_status=v.get("validation_status", "unknown"),
                code_hash=v.get("code_hash", ""),
                code_path=v.get("code_path", ""),
                llm_provider=v.get("llm_provider", ""),
                llm_model=v.get("llm_model", ""),
                smoke_test_status=v.get("smoke_test_status", "unknown"),
                deprecated=v.get("deprecated", False),
            )
            for v in entry.get("versions", [])
        ]
        agents[agent_id] = AgentInfo(
            agent_id=agent_id,
            created_at=entry.get("created_at", ""),
            active_version=entry.get("active_version", ""),
            versions=versions,
            description=entry.get("description", ""),
            agent_type=entry.get("agent_type", ""),
        )
    return agents
