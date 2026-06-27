"""MCP client wrapper.

In v0.1 this is intentionally empty. v0.3 will wrap `mcp.client.session`
to provide a unified interface for the Gateway.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class MCPClient:
    """Placeholder MCP client. Replace with official SDK in v0.3."""

    def __init__(self, server_url: str | None = None) -> None:
        self.server_url = server_url
        log.info("MCPClient initialized (stub). server_url=%s", server_url)

    async def list_tools(self) -> list[dict[str, Any]]:
        return []

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Wire the official mcp SDK in v0.3")
