"""Execution strategies for the Scheduler.

Each strategy decides the order in which ScheduleTasks are executed.
Pluggable — write your own for custom semantics (e.g. DAG, rate-limited).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

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
        for task, outcome in zip(tasks.values(), outcomes, strict=False):
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


class DAGStrategy(ExecutionStrategy):
    """DAG-aware execution: tasks run in topological order, ready tasks concurrently.

    Honors ``task.dependencies``. A task is ready only after all its dependencies
    have succeeded. If a dependency fails, downstream tasks are marked as failed
    with a clear ``dependency_failed`` reason rather than being executed.

    Cycles in the dependency graph are detected and reported as failed results.
    """

    async def execute(
        self,
        tasks: dict[str, ScheduleTask],
        run_one: Callable[[ScheduleTask], Awaitable[ScheduleResult]],
    ) -> dict[str, ScheduleResult]:
        if not tasks:
            return {}

        results: dict[str, ScheduleResult] = {}
        remaining = set(tasks.keys())

        # Validate: every dependency must be a known task.
        for task in tasks.values():
            for dep in task.dependencies:
                if dep not in tasks:
                    results[task.task_id] = ScheduleResult(
                        task_id=task.task_id,
                        agent_id=task.agent_id,
                        success=False,
                        error=f"unknown dependency: {dep!r}",
                    )
                    remaining.discard(task.task_id)

        # Detect cycles using Kahn's algorithm bookkeeping.
        in_degree = self._in_degree(tasks, remaining)
        if self._has_cycle(tasks, in_degree):
            return self._cycle_failure_results(tasks)

        while remaining:
            ready = [
                tasks[tid]
                for tid in remaining
                if all(dep in results and results[dep].success for dep in tasks[tid].dependencies)
            ]
            if not ready:
                # No ready tasks but some remain: either cycle or dependencies already failed.
                for tid in list(remaining):
                    task = tasks[tid]
                    failed_deps = [
                        dep
                        for dep in task.dependencies
                        if dep in results and not results[dep].success
                    ]
                    if failed_deps:
                        results[tid] = ScheduleResult(
                            task_id=task.task_id,
                            agent_id=task.agent_id,
                            success=False,
                            error=f"dependency(s) failed: {failed_deps!r}",
                        )
                        remaining.remove(tid)
                # If anything is still left, it must be a cycle (defensive).
                if remaining:
                    for tid in remaining:
                        results[tid] = ScheduleResult(
                            task_id=tasks[tid].task_id,
                            agent_id=tasks[tid].agent_id,
                            success=False,
                            error="dependency cycle detected",
                        )
                    break
                continue

            # Execute all ready tasks concurrently.
            coros = [run_one(task) for task in ready]
            outcomes = await asyncio.gather(*coros, return_exceptions=True)
            for task, outcome in zip(ready, outcomes, strict=False):
                if isinstance(outcome, Exception):
                    results[task.task_id] = ScheduleResult(
                        task_id=task.task_id,
                        agent_id=task.agent_id,
                        success=False,
                        error=str(outcome),
                    )
                else:
                    results[task.task_id] = outcome
                remaining.remove(task.task_id)

        return results

    @staticmethod
    def _in_degree(tasks: dict[str, ScheduleTask], candidates: set[str]) -> dict[str, int]:
        return {
            tid: sum(1 for dep in tasks[tid].dependencies if dep in candidates)
            for tid in candidates
        }

    @staticmethod
    def _has_cycle(tasks: dict[str, ScheduleTask], in_degree: dict[str, int]) -> bool:
        """Return True if there is a cycle among the candidate tasks."""
        indeg = dict(in_degree)
        queue = [tid for tid, deg in indeg.items() if deg == 0]
        visited = 0
        while queue:
            current = queue.pop()
            visited += 1
            for tid, task in tasks.items():
                if current in task.dependencies and tid in indeg:
                    indeg[tid] -= 1
                    if indeg[tid] == 0:
                        queue.append(tid)
        return visited != len(indeg)

    @staticmethod
    def _cycle_failure_results(tasks: dict[str, ScheduleTask]) -> dict[str, ScheduleResult]:
        return {
            tid: ScheduleResult(
                task_id=task.task_id,
                agent_id=task.agent_id,
                success=False,
                error="dependency cycle detected",
            )
            for tid, task in tasks.items()
        }
