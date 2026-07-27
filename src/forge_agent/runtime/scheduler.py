"""Scheduler — cron-driven trigger that creates TaskRuns on a schedule.

Concrete implementation lands in S3. This protocol is the contract the
web layer uses to register / list / remove scheduled pipeline triggers.

Distinct from ``scheduler/`` (the legacy in-memory execution-strategy
module), which S2 folds into the runtime as an internal execution
component. This module is the *cron* scheduler that fires on time.
"""

from __future__ import annotations

from typing import Any, Protocol


class ScheduledJob:
    """A registered cron schedule that triggers a pipeline.

    Concrete fields (cron expression, next-fire time, enabled flag) land
    in S3. Kept as a placeholder class so the Scheduler protocol can
    reference a stable return type.
    """

    __slots__ = ()


class Scheduler(Protocol):
    """Cron-based scheduler producing TaskRuns."""

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
        """Register a cron-triggered pipeline run."""
        ...

    def remove_job(self, job_id: str) -> bool:
        """Cancel a scheduled job. Returns True if it existed."""
        ...

    def list_jobs(self) -> list[ScheduledJob]:
        """List all registered schedules."""
        ...

    async def start(self) -> None:
        """Begin firing jobs on schedule."""
        ...

    async def stop(self) -> None:
        """Stop the scheduler (graceful)."""
        ...
