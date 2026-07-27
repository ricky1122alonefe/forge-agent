"""ScheduleTask & ScheduleResult — execution units for the runtime executor.

Moved from scheduler/tasks.py (S2.7): the in-memory execution engine
belongs to the runtime layer. These are the units the Executor (formerly
Scheduler) runs via ExecutionStrategy.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport


@dataclass
class ScheduleTask:
    """A single unit of Agent work."""

    task_id: str
    agent_id: str
    context: AgentContext
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    callback: Callable[[AgentReport], Awaitable[None]] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ScheduleResult:
    """The outcome of running a single ScheduleTask."""

    task_id: str
    agent_id: str
    success: bool
    report: AgentReport | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
