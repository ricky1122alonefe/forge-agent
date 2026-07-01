"""Constraint check result."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConstraintSeverity(str, Enum):
    """Violation severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConstraintViolation:
    """A single matched policy."""

    policy_id: str
    policy_name: str
    trigger: str
    severity: str
    matched_text: str = ""
    action: str = "block"


@dataclass
class ConstraintResult:
    """Outcome of running the constraint engine on a piece of content.

    Attributes:
        allowed: True if no BLOCK-level violations were found.
        violations: List of matched policies.
        sanitized: Optional sanitized version of the content.
        metadata: Context (agent_id, run_id, tenant_id, etc.).
    """

    allowed: bool = True
    violations: list[ConstraintViolation] = field(default_factory=list)
    sanitized: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_violation(self, violation: ConstraintViolation) -> None:
        self.violations.append(violation)
        if violation.action == "block":
            self.allowed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "violations": [v.__dict__ for v in self.violations],
            "sanitized": self.sanitized,
            "metadata": self.metadata,
        }
