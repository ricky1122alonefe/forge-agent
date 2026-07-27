"""Executor — in-memory task execution engine (formerly scheduler.Scheduler).

Drives Agent.run() calls. Composable with Pipeline:
the PipelineEngine uses an Executor under the hood.

Moved from scheduler/scheduler.py (S2.7). Renamed file to ``executor.py``
to avoid clashing with ``runtime/scheduler.py`` (the cron-scheduling
Protocol for S3). The class keeps the name ``Scheduler`` for now;
S6 may rename to ``TaskExecutor``.

Distinct from:
- ``runtime/scheduler.py`` — cron Protocol (fires TaskRuns on schedule)
- ``runtime/runner.py``     — async hosting Protocol (persist/retry/callback)
"""

from __future__ import annotations

import logging

from forge_agent.registry.registry import get_registry
from forge_agent.runtime.strategies import ExecutionStrategy, SequentialStrategy
from forge_agent.runtime.tasks import ScheduleResult, ScheduleTask

log = logging.getLogger(__name__)


class Scheduler:
    """In-memory task executor. Composes Strategy + Registry.

    This is the *synchronous* execution engine used by PipelineEngine.
    The async hosting layer (Runner, S3) builds on top of this.
    """

    def __init__(self, *, strategy: ExecutionStrategy | None = None) -> None:
        self.strategy: ExecutionStrategy = strategy or SequentialStrategy()
        self._tasks: dict[str, ScheduleTask] = {}
        self._results: dict[str, ScheduleResult] = {}
        self._registry = get_registry()

    # ------------------------------------------------------------------ API

    def add_task(self, task: ScheduleTask) -> None:
        if task.task_id in self._tasks:
            from forge_agent.exceptions import DuplicateRegistrationError

            raise DuplicateRegistrationError(
                task.task_id, hint="Use a unique task_id for each scheduled task."
            )
        self._tasks[task.task_id] = task

    def clear(self) -> None:
        self._tasks.clear()
        self._results.clear()

    async def run(self) -> dict[str, ScheduleResult]:
        log.info(
            "Executor: running %d task(s) with %s",
            len(self._tasks),
            type(self.strategy).__name__,
        )
        self._results = await self.strategy.execute(self._tasks, self._execute_one)
        return dict(self._results)

    def get_result(self, task_id: str) -> ScheduleResult | None:
        return self._results.get(task_id)

    # ------------------------------------------------------------------ Internal

    async def _execute_one(self, task: ScheduleTask) -> ScheduleResult:
        log.info("Executor: task=%s agent=%s", task.task_id, task.agent_id)
        started = _utcnow()
        try:
            agent = await self._registry.get(task.agent_id)
            report = await agent.run(task.context)
            result = ScheduleResult(
                task_id=task.task_id,
                agent_id=task.agent_id,
                success=True,
                report=report,
                started_at=started,
                finished_at=_utcnow(),
            )
        except Exception as exc:
            log.exception("Task %s failed", task.task_id)
            result = ScheduleResult(
                task_id=task.task_id,
                agent_id=task.agent_id,
                success=False,
                error=str(exc),
                started_at=started,
                finished_at=_utcnow(),
            )
        if task.callback and result.report is not None:
            try:
                await task.callback(result.report)
            except Exception:
                log.exception("Callback for task %s failed", task.task_id)
        return result


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
