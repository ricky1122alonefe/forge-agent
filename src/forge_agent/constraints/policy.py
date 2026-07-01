"""Constraint policy data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TriggerType(str, Enum):
    """Where / when a policy is evaluated."""

    INPUT = "input"  # payload / observation
    OUTPUT = "output"  # agent report text / evidence
    TOOL_CALL = "tool_call"  # a tool is about to be invoked
    DECISION = "decision"  # agent decide() result


class ActionType(str, Enum):
    """What to do when a policy matches."""

    BLOCK = "block"  # reject the action / output
    WARN = "warn"  # allow but flag
    LOG = "log"  # allow, only log


@dataclass
class ConstraintPolicy:
    """A single policy rule.

    Attributes:
        id: Unique identifier.
        name: Human-readable name.
        description: Why the rule exists.
        trigger: Where the rule is evaluated.
        patterns: Strings/regexes to match. Empty list matches nothing.
        action: What to do on match.
        severity: How serious the violation is.
        enabled: Whether the rule is active.
        metadata: Extra tags (category, jurisdiction, etc.).
    """

    id: str
    name: str = ""
    description: str = ""
    trigger: TriggerType = TriggerType.OUTPUT
    patterns: list[str] = field(default_factory=list)
    action: ActionType = ActionType.BLOCK
    severity: str = "medium"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Coerce string enums to real enum values."""
        if isinstance(self.trigger, str):
            object.__setattr__(self, "trigger", TriggerType(self.trigger))
        if isinstance(self.action, str):
            object.__setattr__(self, "action", ActionType(self.action))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConstraintPolicy:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            trigger=data.get("trigger", "output"),
            patterns=list(data.get("patterns", [])),
            action=data.get("action", "block"),
            severity=str(data.get("severity", "medium")),
            enabled=bool(data.get("enabled", True)),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger.value,
            "patterns": self.patterns,
            "action": self.action.value,
            "severity": self.severity,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }
