"""TaskRun — the unit of hosted execution in the forge-agent runtime.

A TaskRun represents one execution of a Pipeline (or single Agent), tracked
through a state machine from submission to a terminal state. Persisted by
``TaskStore``, driven by ``Runner``, triggered by ``TriggerSource``.

State machine::

    pending ──start──► running ──success──► succeeded  (terminal)
           │              │
           │              ├──failure(no retry)──► failed      (terminal)
           │              │
           │              ├──failure(retry)──► retrying ──► running
           │              │
           │              ├──interrupt(restart)──► interrupted ──► pending
           │              │
           └──cancel      └──cancel──► cancelled    (terminal)

Terminal states: succeeded, failed, cancelled. Once terminal, a run cannot
transition further.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class TaskStatus:
    """Lifecycle states for a TaskRun.

    Uses ``str`` constants (not Enum) so the ``status`` field serializes
    to JSON as a plain string without custom encoders.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    INTERRUPTED = "interrupted"


TERMINAL_STATES: frozenset[str] = frozenset(
    {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
)

#: Allowed transitions per source state. Terminal states allow none.
_TRANSITIONS: dict[str, frozenset[str]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.RETRYING,
            TaskStatus.CANCELLED,
            TaskStatus.INTERRUPTED,
        }
    ),
    TaskStatus.RETRYING: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.INTERRUPTED: frozenset({TaskStatus.PENDING, TaskStatus.CANCELLED}),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


class InvalidTaskTransitionError(Exception):
    """Raised when a TaskRun transition is not permitted by the state machine."""

    def __init__(self, run_id: str, current: str, target: str) -> None:
        super().__init__(f"Invalid task transition {current!r}→{target!r} for run {run_id!r}")
        self.run_id = run_id
        self.current = current
        self.target = target


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_run_id() -> str:
    return f"run_{uuid4().hex[:16]}"


@dataclass
class TaskRun:
    """A single hosted execution of a Pipeline.

    Attributes:
        run_id:         Unique id (auto-generated).
        pipeline_id:    Which pipeline to execute.
        tenant_id:      Owning tenant (multi-tenant isolation).
        project_id:     Owning project.
        payload:        Input data passed into the pipeline.
        status:         Current lifecycle state (see TaskStatus).
        result:         Pipeline output (AgentBoard dict) on success.
        error:          Error message on failure.
        attempts:       Number of retries performed (0 = first attempt).
        max_attempts:   Max retries allowed before giving up.
        trigger_source: Origin: manual / schedule / webhook / im.
        trigger_id:     Id of the originating trigger (job_id, event_id...).
        callback_url:   Optional webhook to POST terminal status to.
        created_at / started_at / finished_at: ISO8601 timestamps.
        metadata:       Free-form extra context.
    """

    pipeline_id: str
    tenant_id: str = "default"
    project_id: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=_new_run_id)
    status: str = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    trigger_source: str = "manual"
    trigger_id: str | None = None
    callback_url: str | None = None
    created_at: str = field(default_factory=_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- transitions --------------------------------------------------------

    def transition(self, target: str) -> None:
        """Move to ``target`` state, enforcing the state machine.

        Raises InvalidTaskTransitionError if the move is not allowed.
        Sets started_at on first run, finished_at on terminal.
        """
        allowed = _TRANSITIONS.get(self.status, frozenset())
        if target not in allowed:
            raise InvalidTaskTransitionError(self.run_id, self.status, target)
        if target == TaskStatus.RUNNING and self.started_at is None:
            self.started_at = _now_iso()
        if target in TERMINAL_STATES:
            self.finished_at = _now_iso()
        self.status = target

    def start(self) -> None:
        """pending/retrying → running."""
        self.transition(TaskStatus.RUNNING)

    def succeed(self, result: dict[str, Any] | None = None) -> None:
        """running → succeeded. Optionally attach the pipeline result."""
        if result is not None:
            self.result = result
        self.transition(TaskStatus.SUCCEEDED)

    def fail(self, error: str) -> None:
        """running → failed."""
        self.error = error
        self.transition(TaskStatus.FAILED)

    def schedule_retry(self) -> None:
        """running → retrying, incrementing the attempt counter."""
        self.attempts += 1
        self.transition(TaskStatus.RETRYING)

    def mark_interrupted(self) -> None:
        """running → interrupted (used on crash/restart recovery)."""
        self.transition(TaskStatus.INTERRUPTED)

    def requeue(self) -> None:
        """interrupted → pending (re-queue for execution)."""
        self.transition(TaskStatus.PENDING)

    def cancel(self) -> None:
        """* → cancelled (from any non-terminal state that allows it)."""
        self.transition(TaskStatus.CANCELLED)

    # -- queries ------------------------------------------------------------

    def can_retry(self) -> bool:
        """Whether more retry attempts are permitted."""
        return self.attempts < self.max_attempts

    def is_terminal(self) -> bool:
        """Whether this run has reached a final state."""
        return self.status in TERMINAL_STATES

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "trigger_source": self.trigger_source,
            "trigger_id": self.trigger_id,
            "callback_url": self.callback_url,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRun:
        return cls(
            pipeline_id=data["pipeline_id"],
            tenant_id=data.get("tenant_id", "default"),
            project_id=data.get("project_id", "default"),
            payload=data.get("payload", {}),
            run_id=data.get("run_id") or _new_run_id(),
            status=data.get("status", TaskStatus.PENDING),
            result=data.get("result"),
            error=data.get("error"),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            trigger_source=data.get("trigger_source", "manual"),
            trigger_id=data.get("trigger_id"),
            callback_url=data.get("callback_url"),
            created_at=data.get("created_at") or _now_iso(),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            metadata=data.get("metadata", {}),
        )
