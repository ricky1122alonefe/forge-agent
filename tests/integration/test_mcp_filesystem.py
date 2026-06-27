"""Integration tests for MCP filesystem server via MCPGateway.connect_client().

Tests use mocked MCPClient (no real MCP server needed) to verify:
    - Gateway auto-discovers and registers tools from a client
    - Registered tools can be called through the gateway
    - Permission policies are applied correctly
    - Multiple clients can be connected
    - Disconnect lifecycle works correctly
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from forge_agent.mcp.client import MCPClient, ToolInfo
from forge_agent.mcp.gateway import MCPGateway, get_gateway, reset_gateway
from forge_agent.mcp.permissions import PermissionPolicy


@pytest.fixture(autouse=True)
def _reset():
    """Reset the default gateway before each test."""
    reset_gateway()
    yield
    reset_gateway()


def _make_mock_client(
    tools: list[ToolInfo] | None = None,
    call_results: dict[str, dict] | None = None,
) -> MCPClient:
    """Create a mocked MCPClient that returns predefined tools and results."""
    client = MCPClient.__new__(MCPClient)
    client.server_url = None
    client.command = "mock"
    client.args = []
    client.env = None
    client._session = MagicMock()  # pretend connected
    client._read_stream = None
    client._write_stream = None
    client._cm = None
    client._session_cm = None

    tools = tools or [
        ToolInfo(name="read_file", description="Read a file", input_schema={"type": "object"}),
        ToolInfo(name="write_file", description="Write a file", input_schema={"type": "object"}),
        ToolInfo(name="list_directory", description="List directory", input_schema={"type": "object"}),
    ]
    call_results = call_results or {}

    async def mock_list_tools():
        return tools

    async def mock_call_tool(name, args=None):
        if name in call_results:
            return call_results[name]
        return {"content": [f"mock result for {name}"], "is_error": False}

    async def mock_connect():
        client._session = MagicMock()

    async def mock_disconnect():
        client._session = None

    client.list_tools = mock_list_tools  # type: ignore[assignment]
    client.call_tool = mock_call_tool  # type: ignore[assignment]
    client.connect = mock_connect  # type: ignore[assignment]
    client.disconnect = mock_disconnect  # type: ignore[assignment]

    return client


# ------------------------------------------------------------------ Tests


class TestGatewayConnectClient:
    """Test MCPGateway.connect_client() auto-discovery."""

    @pytest.mark.asyncio
    async def test_connect_client_registers_all_tools(self):
        """connect_client should discover and register all tools from the client."""
        gw = MCPGateway()
        client = _make_mock_client()

        registered = await gw.connect_client(client, server_prefix="fs")

        assert len(registered) == 3
        assert "fs.read_file" in registered
        assert "fs.write_file" in registered
        assert "fs.list_directory" in registered
        assert set(gw.list_tools()) == {"fs.read_file", "fs.write_file", "fs.list_directory"}

    @pytest.mark.asyncio
    async def test_connect_client_without_prefix(self):
        """Without server_prefix, tool names are used as-is."""
        gw = MCPGateway()
        client = _make_mock_client([
            ToolInfo(name="search", description="Search"),
        ])

        registered = await gw.connect_client(client)

        assert registered == ["search"]
        assert "search" in gw.list_tools()

    @pytest.mark.asyncio
    async def test_connect_client_tools_are_callable(self):
        """Registered tools should be callable through the gateway."""
        gw = MCPGateway()
        client = _make_mock_client(
            call_results={"read_file": {"content": ["hello world"], "is_error": False}},
        )

        await gw.connect_client(client, server_prefix="fs")

        result = await gw.call("fs.read_file", {"path": "/tmp/test.txt"})
        assert result["content"] == ["hello world"]
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_connect_client_with_custom_policy(self):
        """Custom policy should be applied to all discovered tools."""
        gw = MCPGateway()
        client = _make_mock_client()

        # Deny all tools
        deny_policy = PermissionPolicy().deny("fs.*", reason="test deny")
        await gw.connect_client(client, server_prefix="fs", policy=deny_policy)

        with pytest.raises(PermissionError, match="test deny"):
            await gw.call("fs.read_file", {})

    @pytest.mark.asyncio
    async def test_connect_client_default_policy_allows(self):
        """Default policy (no policy arg) should allow all discovered tools."""
        gw = MCPGateway()
        client = _make_mock_client()

        await gw.connect_client(client, server_prefix="fs")

        # Should not raise — default policy allows
        result = await gw.call("fs.read_file", {"path": "/tmp/x"})
        assert "content" in result

    @pytest.mark.asyncio
    async def test_connect_client_rejects_non_mcpclient(self):
        """connect_client should reject non-MCPClient objects."""
        gw = MCPGateway()

        with pytest.raises(TypeError, match="Expected MCPClient"):
            await gw.connect_client("not a client")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_connect_client_connects_if_not_connected(self):
        """connect_client should call connect() if client is not connected."""
        gw = MCPGateway()
        client = _make_mock_client()
        # Simulate not connected
        client._session = None

        connect_called = False
        original_connect = client.connect

        async def tracking_connect():
            nonlocal connect_called
            connect_called = True
            await original_connect()

        client.connect = tracking_connect  # type: ignore[assignment]

        await gw.connect_client(client, server_prefix="fs")
        assert connect_called


class TestGatewayMultipleClients:
    """Test connecting multiple MCP clients to a single gateway."""

    @pytest.mark.asyncio
    async def test_multiple_clients_coexist(self):
        """Multiple clients can register tools in the same gateway."""
        gw = MCPGateway()

        fs_client = _make_mock_client([
            ToolInfo(name="read_file", description="Read"),
        ])
        search_client = _make_mock_client([
            ToolInfo(name="web_search", description="Search"),
        ])

        await gw.connect_client(fs_client, server_prefix="fs")
        await gw.connect_client(search_client, server_prefix="tavily")

        tools = gw.list_tools()
        assert "fs.read_file" in tools
        assert "tavily.web_search" in tools

    @pytest.mark.asyncio
    async def test_multiple_clients_tools_callable(self):
        """Tools from different clients are independently callable."""
        gw = MCPGateway()

        fs_client = _make_mock_client(
            [ToolInfo(name="read_file", description="Read")],
            {"read_file": {"content": ["file content"], "is_error": False}},
        )
        search_client = _make_mock_client(
            [ToolInfo(name="web_search", description="Search")],
            {"web_search": {"content": ["search results"], "is_error": False}},
        )

        await gw.connect_client(fs_client, server_prefix="fs")
        await gw.connect_client(search_client, server_prefix="tavily")

        r1 = await gw.call("fs.read_file", {"path": "/tmp/x"})
        r2 = await gw.call("tavily.web_search", {"query": "test"})

        assert r1["content"] == ["file content"]
        assert r2["content"] == ["search results"]


class TestGatewayDisconnect:
    """Test disconnect lifecycle."""

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """disconnect_all should disconnect all clients."""
        gw = MCPGateway()

        c1 = _make_mock_client([ToolInfo(name="a")])
        c2 = _make_mock_client([ToolInfo(name="b")])

        await gw.connect_client(c1, server_prefix="s1")
        await gw.connect_client(c2, server_prefix="s2")

        assert len(gw._clients) == 2

        await gw.disconnect_all()
        assert len(gw._clients) == 0

    @pytest.mark.asyncio
    async def test_disconnect_all_handles_errors(self):
        """disconnect_all should not raise even if a client disconnect fails."""
        gw = MCPGateway()
        client = _make_mock_client()

        async def failing_disconnect():
            raise RuntimeError("disconnect failed")

        client.disconnect = failing_disconnect  # type: ignore[assignment]

        await gw.connect_client(client, server_prefix="fs")
        # Should not raise
        await gw.disconnect_all()


class TestGatewaySingleton:
    """Test get_gateway / reset_gateway singleton."""

    def test_get_gateway_returns_same_instance(self):
        gw1 = get_gateway()
        gw2 = get_gateway()
        assert gw1 is gw2

    def test_reset_gateway_creates_new_instance(self):
        gw1 = get_gateway()
        reset_gateway()
        gw2 = get_gateway()
        assert gw1 is not gw2


class TestGatewayFilesystemScenario:
    """End-to-end scenario: filesystem MCP server integration."""

    @pytest.mark.asyncio
    async def test_filesystem_server_scenario(self):
        """Simulate a full filesystem MCP server integration."""
        gw = MCPGateway()

        # Simulate a filesystem server with typical tools
        fs_tools = [
            ToolInfo(
                name="read_file",
                description="Read file contents",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
            ToolInfo(
                name="write_file",
                description="Write file contents",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            ),
            ToolInfo(
                name="list_directory",
                description="List directory contents",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
            ToolInfo(
                name="move_file",
                description="Move a file",
                input_schema={"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}},
            ),
            ToolInfo(
                name="search_files",
                description="Search for files",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}},
            ),
        ]

        call_results = {
            "read_file": {"content": ["Hello, World!"], "is_error": False},
            "list_directory": {"content": ["file1.txt\nfile2.py\nREADME.md"], "is_error": False},
            "search_files": {"content": ["/tmp/file1.txt\n/tmp/sub/file2.txt"], "is_error": False},
        }

        client = _make_mock_client(fs_tools, call_results)

        # Connect with a policy that allows read operations but denies write
        policy = (
            PermissionPolicy()
            .allow("fs.read_file", reason="read allowed")
            .allow("fs.list_directory", reason="list allowed")
            .allow("fs.search_files", reason="search allowed")
            .deny("fs.write_file", reason="write not allowed")
            .deny("fs.move_file", reason="move not allowed")
        )

        registered = await gw.connect_client(client, server_prefix="fs", policy=policy)
        assert len(registered) == 5

        # Allowed operations should work
        r1 = await gw.call("fs.read_file", {"path": "/tmp/test.txt"})
        assert r1["content"] == ["Hello, World!"]

        r2 = await gw.call("fs.list_directory", {"path": "/tmp"})
        assert "file1.txt" in r2["content"][0]

        r3 = await gw.call("fs.search_files", {"path": "/tmp", "pattern": "*.txt"})
        assert "file1.txt" in r3["content"][0]

        # Denied operations should raise
        with pytest.raises(PermissionError, match="write not allowed"):
            await gw.call("fs.write_file", {"path": "/tmp/x", "content": "data"})

        with pytest.raises(PermissionError, match="move not allowed"):
            await gw.call("fs.move_file", {"source": "/a", "destination": "/b"})

        # Cleanup
        await gw.disconnect_all()
