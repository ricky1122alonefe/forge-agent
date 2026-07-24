"""Tool execution mode for built-in scrapers (P3.4)."""

from __future__ import annotations

import os
from enum import Enum


class ToolMode(str, Enum):
    """How a built-in tool should fetch data."""

    MOCK = "mock"
    REAL = "real"
    AUTO = "auto"


def resolve_tool_mode(explicit: str | None = None) -> ToolMode:
    """Resolve tool mode from explicit config or ``FORGE_AGENT_TOOL_MODE`` env."""
    # Default to AUTO so a "normal program" run tries live data first,
    # and only falls back to fixtures when live probe is unavailable.
    raw = (explicit or os.environ.get("FORGE_AGENT_TOOL_MODE", "auto")).strip().lower()
    try:
        return ToolMode(raw)
    except ValueError:
        return ToolMode.AUTO
