"""ReportFormatter — renders run results into IM messages.

Keeps IM presentation out of core contracts. One formatter can target
multiple platforms (text fallback) or emit platform-specific cards.

S1 ships the protocol; a default text formatter + Feishu card formatter
land in S5.
"""

from __future__ import annotations

from typing import Any, Protocol

from forge_agent.integrations.im.base import IMMessage


class ReportFormatter(Protocol):
    """Renders run results into IM-friendly messages."""

    def format_success(
        self,
        *,
        platform: str,
        chat_id: str,
        run_id: str,
        pipeline_id: str,
        result: dict[str, Any],
    ) -> IMMessage:
        """Format a succeeded run into an IMMessage."""
        ...

    def format_failure(
        self,
        *,
        platform: str,
        chat_id: str,
        run_id: str,
        pipeline_id: str,
        error: str,
    ) -> IMMessage:
        """Format a failed run into an IMMessage."""
        ...
