"""Enums used across the forge-agent contract.

These enums are part of the **stable** public surface. Adding values is
permitted; renumbering or semantic changes are not.
"""

from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    """The semantic verdict of an Agent's analysis.

    Generic (domain-agnostic) so any business can map to it:
        - football  : "lean_home" / "lean_draw" / "lean_away" / "skip"
        - stock     : "buy" / "hold" / "sell" / "skip"
        - monitor   : "ok" / "warning" / "critical" / "skip"
    """

    LEAN_POSITIVE = "lean_positive"
    LEAN_NEUTRAL = "lean_neutral"
    LEAN_NEGATIVE = "lean_negative"
    NEUTRAL = "neutral"
    SAFE = "safe"
    OK = "ok"
    RISK = "risk"
    SKIP = "skip"


class Action(str, Enum):
    """The recommended action after a verdict.

    Generic action vocabulary — domain mapping happens in the Agent.
    """

    EXECUTE = "execute"  # Strong signal, take action
    EXECUTE_CAUTIOUS = "execute_cautious"
    HOLD = "hold"  # Wait / do nothing
    WATCH = "watch"  # Monitor, no action
    ALERT = "alert"  # Raise an alert / notify
    ESCALATE = "escalate"  # Hand off to human or higher-level Agent
    STOP = "stop"  # Hard stop (e.g. hard risk guard)


class AgentStatus(str, Enum):
    """Lifecycle status of an Agent instance."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error"
