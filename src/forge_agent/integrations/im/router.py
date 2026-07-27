"""IMRouter — maps inbound IMEvent to a runtime action.

Parses bot commands (``/run``, ``/status``, ``/list``), resolves the
target pipeline, and submits a TaskRun via the Runner. This is the
bridge between IM inbound and the runtime layer — it depends on
``Runner``, not on Pipeline internals.

Command grammar (S5 will refine)::

    /run <pipeline_id> [payload json]   submit a run, reply with run_id
    /status <run_id>                    query run status
    /list                               list available pipelines
    /help                               show commands

S1 ships the protocol; concrete routing lands in S5.
"""

from __future__ import annotations

from typing import Protocol

from forge_agent.integrations.im.base import IMEvent


class IMRouter(Protocol):
    """Routes inbound IM events to runtime actions."""

    async def handle(self, event: IMEvent) -> str:
        """Process an inbound event; returns a human-readable ack text.

        - ``/run <pipeline>`` → submit TaskRun, reply with run_id
        - ``/status <run_id>`` → query run status
        - ``/list`` → list available pipelines
        - free text → (configurable) default pipeline or help
        """
        ...
