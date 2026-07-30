"""DingTalkAdapter — DingTalk IM platform adapter (S5.5).

Inbound: parses DingTalk robot message events into IMEvent.
Outbound: sends text/actionCard messages via webhook.

DingTalk robot webhook docs:
  POST https://oapi.dingtalk.com/robot/send?access_token=...
  Body: {"msgtype": "text", "text": {"content": "..."}}
  Body: {"msgtype": "actionCard", "actionCard": {...}}

Supports optional HMAC-SHA256 signing for security.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any

from forge_agent.integrations.im.base import IMEvent, IMMessage

log = logging.getLogger(__name__)


class DingTalkAdapter:
    """DingTalk bot adapter. Communicates via webhook URL."""

    def __init__(
        self,
        webhook_url: str,
        *,
        secret: str | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._secret = secret

    @property
    def platform(self) -> str:
        return "dingtalk"

    async def send(self, message: IMMessage) -> bool:
        """Send a message to the DingTalk group via webhook."""
        import httpx

        url = self._signed_url()

        if message.card:
            payload: dict[str, Any] = {
                "msgtype": "actionCard",
                "actionCard": message.card,
            }
        else:
            payload = {"msgtype": "text", "text": {"content": message.text}}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                log.warning("DingTalk send failed: %s", resp.status_code)
                return False
            body = resp.json()
            if body.get("errcode", 0) != 0:
                log.warning("DingTalk send error: %s", body)
                return False
            return True
        except Exception:
            log.exception("DingTalk send failed")
            return False

    def parse_event(self, raw: dict[str, Any]) -> IMEvent:
        """Parse a DingTalk robot message payload into IMEvent."""
        text = raw.get("text", {}).get("content", "").strip()
        chat_id = raw.get("conversationId", raw.get("chatbotUserId", ""))
        user_id = raw.get("senderStaffId", raw.get("senderId", ""))

        command, args = _parse_command(text)

        return IMEvent(
            platform="dingtalk",
            event_type="message",
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            command=command,
            args=args,
            raw=raw,
        )

    def _signed_url(self) -> str:
        """Append HMAC signature if secret is configured."""
        if not self._secret:
            return self._webhook_url

        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self._webhook_url}&timestamp={timestamp}&sign={sign}"


def _parse_command(text: str) -> tuple[str, list[str]]:
    """Extract command and args from text if it starts with /."""
    text = text.strip()
    if not text.startswith("/"):
        return "", []
    parts = text.split()
    return parts[0], parts[1:]
