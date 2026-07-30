"""TaskScheduler — cron-driven trigger that creates TaskRuns on a schedule.

Implements the ``Scheduler`` protocol. Polls for due jobs and submits
them via ``TaskRunner.submit()``.

S3.5 — current schedule format: ``"every:N"`` (every N seconds).
Full cron expression parsing (*/N * * * *) can be added later.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from forge_agent.runtime.task_runner import TaskRunner

log = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A registered schedule that triggers a pipeline."""

    job_id: str
    pipeline_id: str
    cron: str
    tenant_id: str = "default"
    project_id: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)
    callback_url: str | None = None
    next_fire: float = 0.0
    enabled: bool = True


class TaskScheduler:
    """Cron-based scheduler producing TaskRuns via the Runner.

    Usage::

        scheduler = TaskScheduler(runner)
        scheduler.add_job(job_id="daily_report", pipeline_id="report", cron="every:60")
        await scheduler.start()
    """

    def __init__(self, runner: TaskRunner, *, poll_interval: float = 1.0) -> None:
        self._runner = runner
        self._jobs: dict[str, ScheduledJob] = {}
        self._poll_interval = poll_interval
        self._task: asyncio.Task[None] | None = None

    def add_job(
        self,
        *,
        job_id: str,
        pipeline_id: str,
        cron: str,
        tenant_id: str = "default",
        project_id: str = "default",
        payload: dict[str, Any] | None = None,
        callback_url: str | None = None,
    ) -> ScheduledJob:
        """Register a scheduled pipeline run."""
        interval = self._parse_interval(cron)
        job = ScheduledJob(
            job_id=job_id,
            pipeline_id=pipeline_id,
            cron=cron,
            tenant_id=tenant_id,
            project_id=project_id,
            payload=payload or {},
            callback_url=callback_url,
            next_fire=time.time() + interval,
        )
        self._jobs[job_id] = job
        log.info("Added job %s: pipeline=%s cron=%s", job_id, pipeline_id, cron)
        return job

    def remove_job(self, job_id: str) -> bool:
        """Cancel a scheduled job. Returns True if it existed."""
        job = self._jobs.pop(job_id, None)
        if job:
            log.info("Removed job %s", job_id)
            return True
        return False

    def list_jobs(self) -> list[ScheduledJob]:
        """List all registered schedules."""
        return list(self._jobs.values())

    def enable_job(self, job_id: str) -> bool:
        """Re-enable a disabled job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Temporarily disable a job without removing it."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = False
            return True
        return False

    async def start(self) -> None:
        """Begin polling and firing jobs."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        log.info("Scheduler started (poll_interval=%.1fs)", self._poll_interval)

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        log.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Main polling loop."""
        while True:
            await asyncio.sleep(self._poll_interval)
            now = time.time()
            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if now >= job.next_fire:
                    await self._fire(job)
                    interval = self._parse_interval(job.cron)
                    job.next_fire = now + interval

    async def _fire(self, job: ScheduledJob) -> None:
        """Submit a TaskRun for a due job."""
        try:
            run = await self._runner.submit(
                job.pipeline_id,
                tenant_id=job.tenant_id,
                project_id=job.project_id,
                payload=job.payload,
                trigger_source="schedule",
                trigger_id=job.job_id,
                callback_url=job.callback_url,
            )
            log.info("Job %s fired → run %s", job.job_id, run.run_id)
        except Exception:
            log.exception("Job %s failed to fire", job.job_id)

    @staticmethod
    def _parse_interval(cron: str) -> float:
        """Parse schedule expression to interval in seconds.

        Supported formats:
        - ``"every:N"`` — every N seconds (e.g. "every:60")
        - ``"every:Nm"`` — every N minutes
        - ``"every:Nh"`` — every N hours
        - Numeric string — treated as seconds
        """
        cron = cron.strip()
        if cron.startswith("every:"):
            val = cron[6:]
            if val.endswith("m"):
                return float(val[:-1]) * 60
            if val.endswith("h"):
                return float(val[:-1]) * 3600
            return float(val)
        try:
            return float(cron)
        except ValueError:
            log.warning("Unparseable cron %r, defaulting to 60s", cron)
            return 60.0
