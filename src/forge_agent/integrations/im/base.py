"""IMAdapter — protocol for instant-messaging platform integration.

One adapter per platform (Feishu, DingTalk, WeCom, Slack). Adapters are
plugins: they translate platform-specific events into ``IMEvent`` and send
``IMMessage`` back. They **never** touch Pipeline / Agent directly — all
triggering goes through the runtime layer's trigger / callback hooks.

Inbound flow::

    platform webhook ─► adapter.parse_event() ─► IMEvent ─► IMRouter ─► Runner

Outbound flow::

    Runner callback ─► ReportFormatter ─► IMMessage ─► adapter.send()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class IMEvent:
    """An inbound IM event (message, @mention, command).

    Platform-agnostic: every adapter normalizes its raw payload into this
    shape so the IMRouter doesn't need to know which platform fired it.
    """

    platform: str
    event_type: str  # message / mention / command / callback
    chat_id: str  # conversation / channel id
    user_id: str  # sender id
    text: str  # message text
    command: str = ""  # parsed command (e.g. "/run") if applicable
    args: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class IMMessage:
    """An outbound message to send to an IM platform."""

    platform: str
    chat_id: str
    text: str = ""
    card: dict[str, Any] | None = None  # platform-specific card payload
    mention_users: list[str] = field(default_factory=list)


class IMAdapter(Protocol):
    """Protocol each IM platform adapter implements.

    Adapters are registered with the IMRouter at startup. The router
    dispatches inbound events and routes outbound messages back to the
    originating adapter by ``platform``.
    """

    @property
    def platform(self) -> str:
        """Platform id: feishu / dingtalk / wecom / slack."""
        ...

    async def send(self, message: IMMessage) -> bool:
        """Send an outbound message. Returns True on success."""
        ...

    def parse_event(self, raw: dict[str, Any]) -> IMEvent:
        """Parse a platform-specific webhook payload into a normalized IMEvent."""
        ...
