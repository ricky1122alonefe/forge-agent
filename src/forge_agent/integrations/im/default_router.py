"""DefaultIMRouter — routes inbound IM events to runtime actions (S5.2).

Parses bot commands and delegates to the TaskRunner:
  /run <pipeline_id> [json]  → submit async run
  /status <run_id>            → query run status
  /list                       → list available pipelines
  /help                       → show commands

Depends on Runner (runtime layer), not on Pipeline internals.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from forge_agent.integrations.im.base import IMEvent
from forge_agent.runtime.task_runner import TaskRunner

log = logging.getLogger(__name__)


class DefaultIMRouter:
    """Routes inbound IM events to TaskRunner actions."""

    def __init__(
        self,
        runner: TaskRunner,
        *,
        project_root: Path | None = None,
    ) -> None:
        self._runner = runner
        self._project_root = project_root

    async def handle(self, event: IMEvent) -> str:
        """Process an inbound event; returns human-readable ack text."""
        if event.event_type == "challenge":
            return event.text  # Feishu URL verification

        if not event.command:
            return self._help_text()

        if event.command == "/run":
            return await self._handle_run(event)
        if event.command == "/status":
            return self._handle_status(event)
        if event.command == "/list":
            return self._handle_list()
        if event.command == "/help":
            return self._help_text()

        return f"Unknown command `{event.command}`. Type /help for available commands."

    async def _handle_run(self, event: IMEvent) -> str:
        if not event.args:
            return "Usage: /run <pipeline_id> [payload json]"

        pipeline_id = event.args[0]
        payload: dict[str, Any] = {}

        if len(event.args) > 1:
            try:
                payload = json.loads(" ".join(event.args[1:]))
            except json.JSONDecodeError:
                return '❌ Invalid JSON payload. Example: /run my_pipe {"q": "hello"}'

        try:
            run = await self._runner.submit(
                pipeline_id,
                payload=payload,
                trigger_source="im",
                trigger_id=event.raw.get("event_id", event.chat_id),
                callback_url=None,
            )
        except Exception as exc:
            log.exception("IM /run failed")
            return f"❌ Failed to submit: {exc}"

        # Stamp chat_id in metadata for callback
        run.metadata["im_chat_id"] = event.chat_id
        run.metadata["im_platform"] = event.platform
        self._runner.store.update(run)

        return (
            f"✅ Submitted run `{run.run_id}` for pipeline `{pipeline_id}`\n"
            f"Check status: /status {run.run_id}"
        )

    def _handle_status(self, event: IMEvent) -> str:
        if not event.args:
            return "Usage: /status <run_id>"
        run_id = event.args[0]
        run = self._runner.get(run_id)
        if run is None:
            return f"Run `{run_id}` not found"

        lines = [f"Run `{run.run_id}`: **{run.status}**"]
        if run.pipeline_id:
            lines.append(f"Pipeline: {run.pipeline_id}")
        if run.attempts > 0:
            lines.append(f"Attempts: {run.attempts}/{run.max_attempts}")
        if run.error:
            lines.append(f"Error: {run.error[:200]}")
        if run.result:
            verdict = run.result.get("chief_summary", {}).get("verdict", "")
            if verdict:
                lines.append(f"Verdict: {verdict}")
        return "\n".join(lines)

    def _handle_list(self) -> str:
        if self._project_root is None:
            return "Pipeline listing not available"
        pipelines_dir = self._project_root / "pipelines"
        if not pipelines_dir.exists():
            return "No pipelines found"
        files = sorted(pipelines_dir.glob("*.yaml"))
        if not files:
            return "No pipelines found"
        names = [f.stem for f in files]
        return "📋 Pipelines:\n" + "\n".join(f"  • {n}" for n in names)

    @staticmethod
    def _help_text() -> str:
        return (
            "🤖 **Commands:**\n"
            "  `/run <pipeline_id> [payload json]` — submit a run\n"
            "  `/status <run_id>` — query run status\n"
            "  `/list` — list available pipelines\n"
            "  `/help` — show this help"
        )
