"""MCP client wrapper — wraps the official ``mcp`` SDK.

Provides a unified interface for the Gateway to discover and invoke tools
on any MCP server (stdio or SSE transport).

When the ``mcp`` package is not installed, the client falls back to a
stub that returns empty results / raises ``ImportError`` on call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing the official mcp SDK (optional dependency)
# ---------------------------------------------------------------------------
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import Tool, CallToolResult, TextContent

    _HAS_MCP_SDK = True
except ImportError:
    _HAS_MCP_SDK = False


def has_mcp_sdk() -> bool:
    """Return True if the official ``mcp`` package is installed."""
    return _HAS_MCP_SDK


# ---------------------------------------------------------------------------
# Tool info dataclass (SDK-agnostic)
# ---------------------------------------------------------------------------

@dataclass
class ToolInfo:
    """SDK-agnostic representation of a tool discovered via MCP."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


# ---------------------------------------------------------------------------
# MCPClient
# ---------------------------------------------------------------------------

class MCPClient:
    """MCP client that wraps the official ``mcp`` SDK.

    Usage::

        async with MCPClient.from_stdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]) as client:
            tools = await client.list_tools()
            result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})

    When the ``mcp`` package is not installed, ``list_tools()`` returns ``[]``
    and ``call_tool()`` raises ``ImportError``.
    """

    def __init__(
        self,
        server_url: str | None = None,
        *,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.server_url = server_url
        self.command = command
        self.args = args or []
        self.env = env
        self._session: Any | None = None
        self._read_stream: Any | None = None
        self._write_stream: Any | None = None
        self._cm: Any | None = None  # context manager for stdio_client
        self._session_cm: Any | None = None  # context manager for ClientSession
        log.info(
            "MCPClient initialized. sdk=%s, command=%s, server_url=%s",
            _HAS_MCP_SDK,
            command,
            server_url,
        )

    # ---- Factory methods ----

    @classmethod
    def from_stdio(
        cls,
        command: str,
        args: list[str] | None = None,
        *,
        env: dict[str, str] | None = None,
    ) -> MCPClient:
        """Create a client that connects to an MCP server via stdio transport."""
        return cls(command=command, args=args or [], env=env)

    @classmethod
    def from_url(cls, server_url: str) -> MCPClient:
        """Create a client that connects to an MCP server via URL (SSE)."""
        return cls(server_url=server_url)

    # ---- Async context manager ----

    async def __aenter__(self) -> MCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.disconnect()

    # ---- Connection lifecycle ----

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        if not _HAS_MCP_SDK:
            log.warning("mcp SDK not installed; MCPClient will be a no-op stub")
            return

        if self.command:
            await self._connect_stdio()
        elif self.server_url:
            await self._connect_sse()
        else:
            log.warning("No command or server_url specified; MCPClient is a no-op")

    async def _connect_stdio(self) -> None:
        """Connect via stdio transport."""
        params = StdioServerParameters(
            command=self.command,  # type: ignore[arg-type]
            args=self.args,
            env=self.env,
        )
        self._cm = stdio_client(params)
        self._read_stream, self._write_stream = await self._cm.__aenter__()

        self._session_cm = ClientSession(self._read_stream, self._write_stream)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        log.info("MCPClient: connected to stdio server (command=%s)", self.command)

    async def _connect_sse(self) -> None:
        """Connect via SSE transport."""
        try:
            from mcp.client.sse import sse_client

            self._cm = sse_client(self.server_url)  # type: ignore[arg-type]
            self._read_stream, self._write_stream = await self._cm.__aenter__()

            self._session_cm = ClientSession(self._read_stream, self._write_stream)
            self._session = await self._session_cm.__aenter__()
            await self._session.initialize()
            log.info("MCPClient: connected to SSE server (url=%s)", self.server_url)
        except ImportError:
            log.error("mcp SSE client not available")
            raise

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                log.debug("Error closing session context manager", exc_info=True)
            self._session_cm = None
            self._session = None

        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                log.debug("Error closing transport context manager", exc_info=True)
            self._cm = None
            self._read_stream = None
            self._write_stream = None

        log.info("MCPClient: disconnected")

    # ---- Tool operations ----

    @property
    def is_connected(self) -> bool:
        """Return True if the client has an active session."""
        return self._session is not None

    async def list_tools(self) -> list[ToolInfo]:
        """Discover tools available on the connected MCP server.

        Returns a list of ``ToolInfo`` objects. Returns ``[]`` if not connected
        or if the mcp SDK is not installed.
        """
        if not self._session:
            return []

        try:
            result = await self._session.list_tools()
            tools: list[ToolInfo] = []
            for tool in result.tools:
                tools.append(
                    ToolInfo(
                        name=tool.name,
                        description=getattr(tool, "description", "") or "",
                        input_schema=getattr(tool, "inputSchema", None)
                        or getattr(tool, "input_schema", None)
                        or {},
                    )
                )
            log.info("MCPClient: discovered %d tools", len(tools))
            return tools
        except Exception:  # noqa: BLE001
            log.exception("MCPClient: list_tools failed")
            return []

    async def call_tool(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a tool on the connected MCP server.

        Args:
            name: Tool name (as returned by ``list_tools()``).
            args: Arguments to pass to the tool.

        Returns:
            A dict with ``content`` (list of text content) and ``is_error`` flag.

        Raises:
            ImportError: If the mcp SDK is not installed.
            ConnectionError: If not connected to a server.
            RuntimeError: If the tool call fails.
        """
        if not _HAS_MCP_SDK:
            raise ImportError(
                "The 'mcp' package is required for MCP tool calls. "
                "Install it with: pip install 'forge-agent[mcp]'"
            )

        if not self._session:
            raise ConnectionError("MCPClient is not connected. Call connect() first.")

        try:
            result: CallToolResult = await self._session.call_tool(name, arguments=args or {})

            # Extract text content from the result
            content_parts: list[str] = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_parts.append(item.text)
                else:
                    content_parts.append(str(item))

            return {
                "content": content_parts,
                "is_error": getattr(result, "isError", False),
                "raw": result,
            }
        except Exception as exc:
            log.exception("MCPClient: call_tool(%s) failed", name)
            raise RuntimeError(f"MCP tool call failed: {exc}") from exc

    # ---- Convenience: list tools as dicts (backward compat) ----

    async def list_tools_as_dicts(self) -> list[dict[str, Any]]:
        """Return tools as a list of dicts (backward-compatible format)."""
        tools = await self.list_tools()
        return [t.to_dict() for t in tools]
