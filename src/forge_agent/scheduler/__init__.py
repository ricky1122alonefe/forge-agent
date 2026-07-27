"""Deprecated: import from forge_agent.runtime instead.

This shim keeps existing imports working during the S2 migration.
- Scheduler → forge_agent.runtime.executor
- Strategies → forge_agent.runtime.strategies
- ScheduleTask / ScheduleResult → forge_agent.runtime.tasks
"""

from __future__ import annotations

from forge_agent.runtime.executor import Scheduler  # noqa: F401
from forge_agent.runtime.strategies import (  # noqa: F401
    DAGStrategy,
    ExecutionStrategy,
    ParallelStrategy,
    PriorityStrategy,
    SequentialStrategy,
)
from forge_agent.runtime.tasks import ScheduleResult, ScheduleTask  # noqa: F401
