"""Execution strategies for the Scheduler.

Each strategy decides the order in which ScheduleTasks are executed.
Pluggable — write your own for custom semantics (e.g. DAG, rate-limited).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from forge_agent.scheduler.tasks import ScheduleResult, ScheduleTask

log = logging.getLogger(__name__)


class ExecutionStrategy:
    """Base class for execution strategies."""

    async def execute(
        self,
        tasks: dict[str, ScheduleTask],
        run_one: Callable[[ScheduleTask], Awaitable[ScheduleResult]],
    ) -> dict[str, ScheduleResult]:
        raise NotImplementedError


class SequentialStrategy(ExecutionStrategy):
    """Run tasks one after another in insertion order. Deterministic."""

    async def execute(
        self,
        tasks: dict[str, ScheduleTask],
        run_one: Callable[[ScheduleTask], Awaitable[ScheduleResult]],
    ) -> dict[str, ScheduleResult]:
        results: dict[str, ScheduleResult] = {}
        for task in tasks.values():
            results[task.task_id] = await run_one(task)
        return results


class ParallelStrategy(ExecutionStrategy):
    """Run all tasks concurrently with asyncio.gather. Failures don't cancel peers."""

    async def execute(
        self,
        tasks: dict[str, ScheduleTask],
        run_one: Callable[[ScheduleTask], Awaitable[ScheduleResult]],
    ) -> dict[str, ScheduleResult]:
        coros = [run_one(t) for t in tasks.values()]
        outcomes = await asyncio.gather(*coros, return_exceptions=True)
        results: dict[str, ScheduleResult] = {}
        for task, outcome in zip(tasks.values(), outcomes):
            if isinstance(outcome, Exception):
                results[task.task_id] = ScheduleResult(
                    task_id=task.task_id,
                    agent_id=task.agent_id,
                    success=False,
                    error=str(outcome),
                )
            else:
                results[task.task_id] = outcome
        return results


class PriorityStrategy(ExecutionStrategy):
    """Higher priority first; ties broken by created_at."""

    async def execute(
        self,
        tasks: dict[str, ScheduleTask],
        run_one: Callable[[ScheduleTask], Awaitable[ScheduleResult]],
    ) -> dict[str, ScheduleResult]:
        ordered = sorted(
            tasks.values(),
            key=lambda t: (-t.priority, t.created_at),
        )
        results: dict[str, ScheduleResult] = {}
        for task in ordered:
            results[task.task_id] = await run_one(task)
        return results
