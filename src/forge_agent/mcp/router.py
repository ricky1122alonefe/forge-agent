"""MCP router — picks the right tool when given a free-form intent.

Stub for v0.1; v0.3+ will use embeddings + LLM to pick tools.
"""

from __future__ import annotations

import logging
from typing import Any

from forge_agent.mcp.gateway import MCPGateway, get_gateway

log = logging.getLogger(__name__)


class MCPRouter:
    def __init__(self, gateway: MCPGateway | None = None) -> None:
        self.gateway = gateway or get_gateway()

    def route(self, intent: str, available: list[str] | None = None) -> str | None:
        """Naive: pick a tool whose name shares a token with the intent."""
        available = available or self.gateway.list_tools()
        intent_tokens = set(intent.lower().split())
        best: tuple[int, str] | None = None
        for name in available:
            tokens = set(name.lower().replace(".", " ").split("_"))
            overlap = len(intent_tokens & tokens)
            if overlap and (best is None or overlap > best[0]):
                best = (overlap, name)
        return best[1] if best else None

    async def dispatch(self, intent: str, args: dict[str, Any]) -> dict[str, Any] | None:
        tool = self.route(intent)
        if not tool:
            log.warning("MCPRouter: no tool matched intent=%r", intent)
            return None
        return await self.gateway.call(tool, args)
