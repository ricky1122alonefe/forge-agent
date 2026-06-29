"""Common type aliases used throughout forge-agent."""

from __future__ import annotations

from typing import Any, TypeAlias

# A domain-agnostic JSON-serializable value
JSONValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None

# A free-form observation produced by an Agent
Observation: TypeAlias = dict[str, Any]

# A free-form decision produced by an Agent
Decision: TypeAlias = dict[str, Any]
