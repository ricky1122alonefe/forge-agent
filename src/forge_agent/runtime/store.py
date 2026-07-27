"""TaskStore — persistence protocol for TaskRuns.

Concrete SQLite implementation lands in S3 (reusing ``SQLiteConnection``).
This protocol defines the contract the Runner depends on:
create / get / update / list / recover.
"""

from __future__ import annotations

from typing import Protocol

from forge_agent.runtime.models import TaskRun


class TaskStore(Protocol):
    """Persistent store for TaskRun records."""

    def create(self, run: TaskRun) -> None:
        """Insert a new TaskRun (run_id must not already exist)."""
        ...

    def get(self, run_id: str) -> TaskRun | None:
        """Fetch a TaskRun by id, or None if missing."""
        ...

    def update(self, run: TaskRun) -> None:
        """Persist updated fields (status / result / error / timestamps)."""
        ...

    def list(
        self,
        *,
        tenant_id: str | None = None,
        project_id: str | None = None,
        pipeline_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskRun]:
        """List runs with optional filters, newest first."""
        ...

    def list_by_status(self, status: str) -> list[TaskRun]:
        """Fetch all runs in a given status (used for crash recovery)."""
        ...

    def delete(self, run_id: str) -> bool:
        """Delete a run. Returns True if a row was removed."""
        ...
