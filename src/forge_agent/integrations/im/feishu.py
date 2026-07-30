"""FeishuAdapter — Feishu (Lark) IM platform adapter (S5.1).

Inbound: parses Feishu bot message events into IMEvent.
Outbound: sends text/interactive-card messages via webhook.

Feishu bot webhook docs:
  POST https://open.feishu.cn/open-apis/bot/v2/hook/{token}
  Body: {"msg_type": "text", "content": {"text": "..."}}
  Body: {"msg_type": "interactive", "card": {...}}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from forge_agent.integrations.im.base import IMEvent, IMMessage

log = logging.getLogger(__name__)


class FeishuAdapter:
    """Feishu bot adapter. Communicates via webhook URL."""

    def __init__(
        self,
        webhook_url: str,
        *,
        verify_token: str | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._verify_token = verify_token

    @property
    def platform(self) -> str:
        return "feishu"

    async def send(self, message: IMMessage) -> bool:
        """Send a message to the Feishu group via webhook."""
        import httpx

        if message.card:
            payload: dict[str, Any] = {"msg_type": "interactive", "card": message.card}
        else:
            payload = {"msg_type": "text", "content": {"text": message.text}}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._webhook_url, json=payload)
            if resp.status_code != 200:
                log.warning("Feishu send failed: %s %s", resp.status_code, resp.text[:200])
                return False
            body = resp.json()
            if body.get("code", 0) != 0:
                log.warning("Feishu send error: %s", body)
                return False
            return True
        except Exception:
            log.exception("Feishu send failed")
            return False

    def parse_event(self, raw: dict[str, Any]) -> IMEvent:
        """Parse a Feishu event payload into a normalized IMEvent.

        Supports Feishu v2 event schema (im.message.receive_v1).
        """
        header = raw.get("header", {})
        event = raw.get("event", {})
        event_type = header.get("event_type", "message")

        # URL verification challenge
        if "challenge" in raw:
            return IMEvent(
                platform="feishu",
                event_type="challenge",
                chat_id="",
                user_id="",
                text=raw.get("challenge", ""),
                raw=raw,
            )

        message = event.get("message", {})
        chat_id = message.get("chat_id", "")
        content = message.get("content", "{}")

        if isinstance(content, str):
            try:
                content_dict = json.loads(content)
            except json.JSONDecodeError:
                content_dict = {"text": content}
        elif isinstance(content, dict):
            content_dict = content
        else:
            content_dict = {}

        text = content_dict.get("text", "") if isinstance(content_dict, dict) else str(content)

        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        user_id = sender_id.get("open_id", sender_id.get("union_id", ""))

        command, args = _parse_command(text)

        return IMEvent(
            platform="feishu",
            event_type=event_type,
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            command=command,
            args=args,
            raw=raw,
        )


def _parse_command(text: str) -> tuple[str, list[str]]:
    """Extract command and args from text if it starts with /."""
    text = text.strip()
    if not text.startswith("/"):
        return "", []
    parts = text.split()
    return parts[0], parts[1:]
