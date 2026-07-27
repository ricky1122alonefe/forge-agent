"""Runner — async execution engine for TaskRuns.

Submits a run (returns the run record immediately with status=pending),
executes in the background, updates status via TaskStore, applies
RetryPolicy on failure, and fires callbacks on terminal states.

Concrete implementation lands in S3. This protocol is the contract that
triggers (manual / schedule / webhook / im) depend on — they call
``submit()`` and walk away.
"""

from __future__ import annotations

from typing import Any, Protocol

from forge_agent.runtime.models import TaskRun
from forge_agent.runtime.store import TaskStore


class Runner(Protocol):
    """Async task execution engine."""

    @property
    def store(self) -> TaskStore:
        """Backing persistence for run records."""
        ...

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

        Returns immediately with the run record (status=pending). The
        caller polls ``get()`` or listens for a callback to learn the
        terminal outcome.
        """
        ...

    async def cancel(self, run_id: str) -> bool:
        """Request cancellation of a run. Returns True if accepted."""
        ...

    def get(self, run_id: str) -> TaskRun | None:
        """Synchronous status lookup (reads from the store)."""
        ...

    async def recover(self) -> int:
        """On startup, mark crashed 'running' runs as 'interrupted'.

        Returns the count of runs recovered. Call once at boot before
        accepting new submissions.
        """
        ...
