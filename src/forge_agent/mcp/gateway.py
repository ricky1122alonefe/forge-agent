"""MCP Gateway — single point of access to MCP servers.

In v0.1 this is a stub. In v0.3 we wire the official `mcp` SDK:
    - MultiServerMCPClient for connecting to multiple MCP servers.
    - Tool discovery (list_tools) cached per agent.
    - Per-tool call() with policy enforcement.
    - Session reuse and rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from forge_agent.mcp.permissions import PermissionPolicy

log = logging.getLogger(__name__)

# Tool handler signature: async (args: dict) -> dict
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class MCPGateway:
    """Registry of tools, each with a permission policy.

    Tools are addressed by `server.tool` (e.g. `tavily.search`).
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}
        self._policies: dict[str, PermissionPolicy] = {}
        self._lock = asyncio.Lock()

    def register_tool(
        self,
        name: str,
        handler: ToolHandler,
        *,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._tools[name] = handler
        self._policies[name] = policy or PermissionPolicy()
        log.info("MCPGateway: registered tool %s", name)

    def set_policy(self, name: str, policy: PermissionPolicy) -> None:
        if name not in self._tools:
            raise KeyError(f"Tool {name!r} not registered")
        self._policies[name] = policy

    async def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in self._tools:
            raise KeyError(f"Tool {name!r} not registered")
        policy = self._policies[name]
        allowed, reason = policy.check(name)
        if not allowed:
            raise PermissionError(f"Tool {name!r} denied: {reason}")
        handler = self._tools[name]
        return await handler(args or {})

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# Module-level default gateway (singleton)
_default: MCPGateway | None = None


def get_gateway() -> MCPGateway:
    global _default
    if _default is None:
        _default = MCPGateway()
    return _default
