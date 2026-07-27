"""forge-agent runtime — task orchestration & hosting layer.

Provides async, persistent, retryable execution of Pipelines:

    TriggerSource ─► Runner ─► Pipeline ─► TaskRun (persisted)

This is the layer that turns forge-agent from "click-to-run demo" into a
"hosted platform": runs survive restarts, retry on failure, fire on
schedules, and callback to IM/webhook.

See PLAN.md v5 §三 for the capability stack. S1 ships the skeleton +
state machine; concrete store/runner/scheduler land in S3.
"""

from forge_agent.runtime.models import (
    InvalidTaskTransitionError,
    TaskRun,
    TaskStatus,
)
from forge_agent.runtime.retry import RetryPolicy
from forge_agent.runtime.triggers import TriggerType

__all__ = [
    "InvalidTaskTransitionError",
    "RetryPolicy",
    "TaskRun",
    "TaskStatus",
    "TriggerType",
]
