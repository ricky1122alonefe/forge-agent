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
        self._clients: list[Any] = []  # connected MCPClient instances
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

    # ------------------------------------------------------------------
    # MCPClient integration — auto-discover & register tools
    # ------------------------------------------------------------------

    async def connect_client(
        self,
        client: Any,
        *,
        server_prefix: str | None = None,
        policy: PermissionPolicy | None = None,
    ) -> list[str]:
        """Connect an MCPClient and register all its tools in this gateway.

        Args:
            client: An ``MCPClient`` instance (already connected or not).
            server_prefix: Optional prefix for tool names (e.g. ``"fs"``).
                If ``None``, tool names are used as-is from the server.
            policy: Default permission policy for discovered tools.
                If ``None``, all discovered tools are allowed.

        Returns:
            List of registered tool names.
        """
        from forge_agent.mcp.client import MCPClient

        if not isinstance(client, MCPClient):
            raise TypeError(f"Expected MCPClient, got {type(client).__name__}")

        # Connect if not already connected
        if not client.is_connected:
            await client.connect()

        # Discover tools
        tool_infos = await client.list_tools()
        registered: list[str] = []

        for info in tool_infos:
            # Build the gateway-level tool name
            tool_name = f"{server_prefix}.{info.name}" if server_prefix else info.name

            # Create a handler closure that delegates to the client
            handler = self._make_client_handler(client, info.name)

            # Default policy: allow all discovered tools
            tool_policy = policy if policy is not None else PermissionPolicy().allow(tool_name)
            self.register_tool(tool_name, handler, policy=tool_policy)
            registered.append(tool_name)

        self._clients.append(client)
        log.info(
            "MCPGateway: connected client, registered %d tools: %s",
            len(registered),
            registered,
        )
        return registered

    @staticmethod
    def _make_client_handler(client: Any, tool_name: str) -> ToolHandler:
        """Create a handler closure that delegates to an MCPClient."""

        async def handler(args: dict[str, Any]) -> dict[str, Any]:
            return await client.call_tool(tool_name, args)

        return handler

    async def disconnect_all(self) -> None:
        """Disconnect all connected MCP clients."""
        for client in self._clients:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                log.debug("Error disconnecting client", exc_info=True)
        self._clients.clear()
        log.info("MCPGateway: disconnected all clients")


# Module-level default gateway (singleton)
_default: MCPGateway | None = None


def get_gateway() -> MCPGateway:
    global _default
    if _default is None:
        _default = MCPGateway()
    return _default


def reset_gateway() -> None:
    """Reset the default gateway (for testing)."""
    global _default
    _default = None
