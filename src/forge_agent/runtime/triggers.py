"""Trigger sources — how a TaskRun enters the runtime.

``TriggerType`` enumerates the entry points. ``TriggerSource`` is the
protocol each concrete trigger (manual button, cron scheduler, webhook,
IM event) implements to build a pending TaskRun for the Runner.

Concrete triggers land in S3; this module defines the contract.
"""

from __future__ import annotations

from typing import Any, Protocol

from forge_agent.runtime.models import TaskRun


class TriggerType:
    """Origin categories for TaskRuns."""

    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    IM = "im"


class TriggerSource(Protocol):
    """A source that builds TaskRuns for the Runner to execute.

    Implementations (S3): ManualTrigger, ScheduleTrigger, WebhookTrigger,
    IMTrigger. Each knows how to stamp ``trigger_source`` / ``trigger_id``
    onto the run it produces.
    """

    @property
    def trigger_type(self) -> str:
        """One of TriggerType constants."""
        ...

    def build_run(
        self,
        pipeline_id: str,
        *,
        tenant_id: str = "default",
        project_id: str = "default",
        payload: dict[str, Any] | None = None,
        callback_url: str | None = None,
    ) -> TaskRun:
        """Construct a pending TaskRun stamped with this trigger's metadata."""
        ...
