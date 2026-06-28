"""Mission abstraction: a scheduled execution of a Team.

A Mission binds a Team to a concrete task with a payload and optional schedule.
It is the unit of work that `TeamRunner` executes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge_agent.core.team import Team


@dataclass
class Mission:
    """A scheduled execution of a Team.

    Attributes:
        mission_id: Unique identifier for this mission.
        name: Human-readable name.
        description: Optional description of what the mission does.
        team: The Team that executes the mission.
        schedule: Optional cron expression (e.g. "0 9 * * *").
        interval_seconds: Optional fixed interval between runs.
        payload: Mission-specific payload merged with the team's payload.
        enabled: Whether the mission is currently active.
        metadata: Free-form metadata for UI / tooling.
    """

    mission_id: str
    name: str
    team: Team
    description: str = ""
    schedule: str | None = None
    interval_seconds: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "mission_id": self.mission_id,
            "name": self.name,
            "description": self.description,
            "team": self.team.to_dict(),
            "schedule": self.schedule,
            "interval_seconds": self.interval_seconds,
            "payload": dict(self.payload),
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Mission:
        """Deserialize from a dict."""
        return cls(
            mission_id=data["mission_id"],
            name=data["name"],
            description=data.get("description", ""),
            team=Team.from_dict(data["team"]),
            schedule=data.get("schedule"),
            interval_seconds=data.get("interval_seconds"),
            payload=dict(data.get("payload", {})),
            enabled=data.get("enabled", True),
            metadata=dict(data.get("metadata", {})),
        )
