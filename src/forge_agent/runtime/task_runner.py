"""TaskRunner — concrete async execution engine for TaskRuns.

Implements the ``Runner`` protocol. Submits a run (returns immediately
with status=pending), executes in the background via ``PipelineExecutor``,
applies ``RetryPolicy`` on failure, and fires callbacks on terminal states.

Covers S3.2 (async submit), S3.4 (retry), S3.6 (recover), S3.7 (callback).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from forge_agent.runtime.models import TaskRun, TaskStatus
from forge_agent.runtime.retry import RetryPolicy
from forge_agent.runtime.store import TaskStore

log = logging.getLogger(__name__)


class PipelineExecutor(Protocol):
    """Executes a pipeline and returns its result.

    The Runner depends on this protocol, not on PipelineEngine directly,
    so the runner is testable without the full pipeline stack.
    """

    async def execute(
        self,
        pipeline_id: str,
        payload: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        """Execute *pipeline_id* with *payload*. Return result dict.

        Raise on failure — the Runner handles retry logic.
        """
        ...


class CallbackHandler(Protocol):
    """Notified when a run reaches a terminal state."""

    async def on_terminal(self, run: TaskRun) -> None:
        """Called after a run succeeds, fails, or is cancelled."""
        ...


class TaskRunner:
    """Async task execution engine.

    Usage::

        runner = TaskRunner(store=SQLiteTaskStore(...), executor=my_executor)
        run = await runner.submit("my_pipeline", payload={"q": "hello"})
        # ... later ...
        run = runner.get(run.run_id)  # check status
    """

    def __init__(
        self,
        store: TaskStore,
        executor: PipelineExecutor,
        *,
        retry: RetryPolicy | None = None,
        callback: CallbackHandler | None = None,
    ) -> None:
        self._store = store
        self._executor = executor
        self._retry = retry or RetryPolicy()
        self._callback = callback
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def store(self) -> TaskStore:
        return self._store

    async def submit(
        self,
        pipeline_id: str,
        *,
        tenant_id: str = "default",
        project_id: str = "default",
        payload: dict[str, Any] | None = None,
        trigger_source: str = "manual",
        trigger_id: str | None = None,
        callback_url: str | None = None,
    ) -> TaskRun:
        """Create a pending TaskRun and start background execution.

        Returns immediately with the run record (status=pending).
        """
        run = TaskRun(
            pipeline_id=pipeline_id,
            tenant_id=tenant_id,
            project_id=project_id,
            payload=payload or {},
            trigger_source=trigger_source,
            trigger_id=trigger_id,
            callback_url=callback_url,
            max_attempts=self._retry.max_attempts,
        )
        self._store.create(run)
        task = asyncio.create_task(self._execute(run))
        self._tasks[run.run_id] = task
        return run

    async def cancel(self, run_id: str) -> bool:
        """Request cancellation. Returns True if accepted."""
        run = self._store.get(run_id)
        if run is None or run.is_terminal():
            return False
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        # Not currently executing — mark cancelled directly
        run.cancel()
        self._store.update(run)
        if self._callback:
            await self._callback.on_terminal(run)
        return True

    def get(self, run_id: str) -> TaskRun | None:
        """Synchronous status lookup."""
        return self._store.get(run_id)

    async def recover(self) -> int:
        """Mark crashed 'running' runs as 'interrupted'. Call at boot."""
        running = self._store.list_by_status(TaskStatus.RUNNING)
        for run in running:
            run.mark_interrupted()
            self._store.update(run)
        if running:
            log.warning("Recovered %d interrupted run(s)", len(running))
        return len(running)

    async def _execute(self, run: TaskRun) -> None:
        """Background execution loop with retry."""
        try:
            run.start()
            self._store.update(run)

            while True:
                try:
                    result = await self._executor.execute(run.pipeline_id, run.payload, run.run_id)
                    run.succeed(result=result)
                    self._store.update(run)
                    break
                except Exception as exc:
                    log.warning("Run %s failed (attempt %d): %s", run.run_id, run.attempts + 1, exc)
                    if run.can_retry() and self._retry.should_retry(run.attempts):
                        run.schedule_retry()
                        self._store.update(run)
                        delay = self._retry.delay_for(run.attempts)
                        await asyncio.sleep(delay)
                        run.start()
                        self._store.update(run)
                        continue
                    run.fail(str(exc))
                    self._store.update(run)
                    break

            if self._callback:
                await self._callback.on_terminal(run)

        except asyncio.CancelledError:
            run.cancel()
            self._store.update(run)
            if self._callback:
                await self._callback.on_terminal(run)
            raise
        finally:
            self._tasks.pop(run.run_id, None)

    async def wait(self, run_id: str, timeout: float = 30.0) -> TaskRun | None:
        """Wait for a run to reach terminal state. Returns the final run."""
        task = self._tasks.get(run_id)
        if task:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        return self._store.get(run_id)
