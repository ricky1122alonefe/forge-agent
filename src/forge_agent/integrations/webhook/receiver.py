"""WebhookReceiver — generic HTTP webhook entry point into the runtime.

Accepts external POST payloads and submits them as TaskRuns. This is the
non-IM counterpart to ``IMRouter``: a uniform trigger for CI systems,
external services, or simple curl-based invocation.

Inbound flow::

    external POST ─► WebhookReceiver.receive() ─► Runner.submit(trigger=webhook)

S1 ships the protocol; concrete receiver (signature verification, FastAPI
route wiring) lands in S3/S4.
"""

from __future__ import annotations

from typing import Any, Protocol


class WebhookReceiver(Protocol):
    """Receives webhook payloads and submits TaskRuns."""

    async def receive(
        self,
        *,
        pipeline_id: str,
        payload: dict[str, Any],
        signature: str | None = None,
        tenant_id: str = "default",
        project_id: str = "default",
    ) -> str:
        """Validate (optional signature) and submit a webhook-triggered run.

        Returns the run_id.
        """
        ...
