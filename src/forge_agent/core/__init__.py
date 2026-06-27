"""Core abstractions: contracts, enums, context, capabilities, and BaseAgent.

This package is the "base layer" of forge-agent.
Everything else (registry, scheduler, pipeline, generator) depends on it,
but it depends on **nothing** else within forge-agent.

The cardinal rule: **changes here ripple to every Agent in the ecosystem,
so the contract is minimal, stable, and extensible.**
"""

from __future__ import annotations

from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Action, AgentStatus, Verdict
from forge_agent.core.report_store import SQLiteReportStore

__all__ = [
    "BaseAgent",
    "AgentReport",
    "AgentBoard",
    "AgentContext",
    "Action",
    "AgentStatus",
    "Verdict",
    "SQLiteReportStore",
]
