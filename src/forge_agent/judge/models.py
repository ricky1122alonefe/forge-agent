"""Judge data models (S6.4 split from __init__.py).

IssueSeverity, JudgeIssue, DimensionScore, JudgeReport — pure data
structures with no business logic. Independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class JudgeIssue:
    """A single issue found by the judge."""

    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.INFO
    agent_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "agent_id": self.agent_id,
            "details": self.details,
        }


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    name: str
    score: float  # 0.0 ~ 1.0
    weight: float = 1.0
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "weight": self.weight,
            "details": self.details,
        }


@dataclass
class JudgeReport:
    """Result of judging an AgentReport or AgentBoard."""

    target_id: str
    target_type: str
    score: float = 0.0
    grade: str = ""
    dimensions: list[DimensionScore] = field(default_factory=list)
    issues: list[JudgeIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "score": round(self.score, 3),
            "grade": self.grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "has_critical": self.has_critical,
            "has_warnings": self.has_warnings,
            "metadata": self.metadata,
        }
