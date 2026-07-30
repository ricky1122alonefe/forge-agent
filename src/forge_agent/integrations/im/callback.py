"""IMCallback — pushes terminal run results to IM (S5.4).

Implements the CallbackHandler protocol. When a TaskRun reaches a
terminal state (succeeded/failed), this callback formats the result
and sends it back to the originating IM chat.

Wiring::

    TaskRunner(callback=IMCallback(adapter, formatter))
    ─► run completes ─► on_terminal(run) ─► formatter ─► adapter.send()

The chat_id is read from run.metadata["im_chat_id"], stamped by
DefaultIMRouter when the /run command is processed.
"""

from __future__ import annotations

import logging

from forge_agent.integrations.im.base import IMAdapter
from forge_agent.integrations.im.formatter import ReportFormatter
from forge_agent.runtime.models import TaskRun, TaskStatus

log = logging.getLogger(__name__)


class IMCallback:
    """Pushes terminal run results to the originating IM chat."""

    def __init__(
        self,
        adapter: IMAdapter,
        formatter: ReportFormatter,
        *,
        default_chat_id: str = "",
    ) -> None:
        self._adapter = adapter
        self._formatter = formatter
        self._default_chat_id = default_chat_id

    async def on_terminal(self, run: TaskRun) -> None:
        chat_id = run.metadata.get("im_chat_id", self._default_chat_id)
        if not chat_id:
            log.debug("Run %s has no IM chat_id, skipping callback", run.run_id)
            return

        if run.status == TaskStatus.SUCCEEDED:
            msg = self._formatter.format_success(
                platform=self._adapter.platform,
                chat_id=chat_id,
                run_id=run.run_id,
                pipeline_id=run.pipeline_id,
                result=run.result or {},
            )
        elif run.status == TaskStatus.FAILED:
            msg = self._formatter.format_failure(
                platform=self._adapter.platform,
                chat_id=chat_id,
                run_id=run.run_id,
                pipeline_id=run.pipeline_id,
                error=run.error or "unknown error",
            )
        else:
            log.debug("Run %s terminal state %s — no IM callback", run.run_id, run.status)
            return

        success = await self._adapter.send(msg)
        if not success:
            log.warning("IM callback send failed for run %s", run.run_id)
