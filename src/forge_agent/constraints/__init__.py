"""Constraint / policy framework for forge-agent.

Provides a generic, pluggable way to enforce platform-level and tenant-level
rules on agent inputs, outputs, and tool calls. Designed to help SaaS operators
prevent abuse, illegal content, or policy violations.
"""

from __future__ import annotations

from forge_agent.constraints.engine import ConstraintEngine
from forge_agent.constraints.policy import ConstraintPolicy, TriggerType
from forge_agent.constraints.result import ConstraintResult, ConstraintSeverity

__all__ = [
    "ConstraintEngine",
    "ConstraintPolicy",
    "ConstraintResult",
    "ConstraintSeverity",
    "TriggerType",
]
