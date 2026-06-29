"""Team abstraction: a group of agents collaborating on a mission.

A Team is a declarative grouping of agent IDs that are executed together.
The actual execution is handled by `TeamRunner` (see `runner.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Team:
    """A team of agents that collaborate on a mission.

    Attributes:
        team_id: Unique identifier for this team.
        name: Human-readable name.
        domain: Business domain (e.g. "stock", "weather", "generic").
        agent_ids: List of registered agent IDs that make up the team.
        chief_id: Optional agent ID that synthesizes the team's output.
        mode: "parallel" or "sequential" execution of member agents.
        payload: Shared context payload passed to every member agent.
        metadata: Free-form metadata for UI / tooling.
    """

    team_id: str
    name: str
    domain: str = "generic"
    agent_ids: list[str] = field(default_factory=list)
    chief_id: str | None = None
    chief_config: dict[str, Any] = field(default_factory=dict)
    mode: str = "parallel"
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in {"parallel", "sequential"}:
            msg = f"Unknown team mode: {self.mode}. Use 'parallel' or 'sequential'."
            raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "team_id": self.team_id,
            "name": self.name,
            "domain": self.domain,
            "agent_ids": list(self.agent_ids),
            "chief_id": self.chief_id,
            "chief_config": dict(self.chief_config),
            "mode": self.mode,
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Team:
        """Deserialize from a dict."""
        return cls(
            team_id=data["team_id"],
            name=data["name"],
            domain=data.get("domain", "generic"),
            agent_ids=list(data.get("agent_ids", [])),
            chief_id=data.get("chief_id"),
            chief_config=dict(data.get("chief_config", {})),
            mode=data.get("mode", "parallel"),
            payload=dict(data.get("payload", {})),
            metadata=dict(data.get("metadata", {})),
        )
