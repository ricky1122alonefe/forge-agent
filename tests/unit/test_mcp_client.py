"""Tests for MCPClient — T2.3.1 接入 mcp 官方 SDK."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from forge_agent.mcp.client import MCPClient, ToolInfo, has_mcp_sdk


# ====================================================================
# ToolInfo tests
# ====================================================================


class TestToolInfo:
    """Tests for the ToolInfo dataclass."""

    def test_basic_creation(self):
        tool = ToolInfo(name="fs.read_file")
        assert tool.name == "fs.read_file"
        assert tool.description == ""
        assert tool.input_schema == {}

    def test_full_creation(self):
        schema = {"type": "object", "properties": {"path": {"type": "string"}}}
        tool = ToolInfo(
            name="fs.read_file",
            description="Read a file from disk",
            input_schema=schema,
        )
        assert tool.name == "fs.read_file"
        assert tool.description == "Read a file from disk"
        assert tool.input_schema == schema

    def test_to_dict(self):
        tool = ToolInfo(name="tavily.search", description="Search the web")
        d = tool.to_dict()
        assert d == {
            "name": "tavily.search",
            "description": "Search the web",
            "input_schema": {},
        }

    def test_to_dict_with_schema(self):
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        tool = ToolInfo(name="search", description="Search", input_schema=schema)
        d = tool.to_dict()
        assert d["input_schema"] == schema


# ====================================================================
# has_mcp_sdk tests
# ====================================================================


class TestHasMcpSdk:
    """Tests for the has_mcp_sdk() function."""

    def test_returns_bool(self):
        result = has_mcp_sdk()
        assert isinstance(result, bool)

    def test_consistent(self):
        assert has_mcp_sdk() == has_mcp_sdk()


# ====================================================================
# MCPClient initialization tests
# ====================================================================


class TestMCPClientInit:
    """Tests for MCPClient initialization and factory methods."""

    def test_default_init(self):
        client = MCPClient()
        assert client.server_url is None
        assert client.command is None
        assert client.args == []
        assert client.env is None
        assert client.is_connected is False

    def test_init_with_server_url(self):
        client = MCPClient(server_url="http://localhost:3000")
        assert client.server_url == "http://localhost:3000"

    def test_init_with_command(self):
        client = MCPClient(command="npx", args=["-y", "server"])
        assert client.command == "npx"
        assert client.args == ["-y", "server"]

    def test_from_stdio(self):
        client = MCPClient.from_stdio("npx", ["-y", "@mcp/fs", "/tmp"])
        assert client.command == "npx"
        assert client.args == ["-y", "@mcp/fs", "/tmp"]
        assert client.server_url is None

    def test_from_stdio_with_env(self):
        client = MCPClient.from_stdio("node", ["server.js"], env={"PORT": "3000"})
        assert client.command == "node"
        assert client.env == {"PORT": "3000"}

    def test_from_url(self):
        client = MCPClient.from_url("http://localhost:8080/sse")
        assert client.server_url == "http://localhost:8080/sse"
        assert client.command is None


# ====================================================================
# MCPClient connection tests (mocked)
# ====================================================================


class TestMCPClientConnection:
    """Tests for MCPClient connection lifecycle with mocked session."""

    async def test_is_connected_false_by_default(self):
        client = MCPClient()
        assert client.is_connected is False

    async def test_is_connected_true_with_session(self):
        client = MCPClient()
        client._session = MagicMock()
        assert client.is_connected is True

    async def test_connect_no_sdk_no_command_no_url(self):
        """connect() with no SDK and no command/url should be a no-op."""
        client = MCPClient()
        await client.connect()
        assert client.is_connected is False

    async def test_disconnect_when_not_connected(self):
        """disconnect() when not connected should be a no-op."""
        client = MCPClient()
        await client.disconnect()  # Should not raise
        assert client.is_connected is False

    async def test_disconnect_cleans_up(self):
        """disconnect() should clean up session and transport."""
        client = MCPClient()
        mock_session_cm = AsyncMock()
        mock_cm = AsyncMock()
        client._session_cm = mock_session_cm
        client._session = MagicMock()
        client._cm = mock_cm
        client._read_stream = MagicMock()
        client._write_stream = MagicMock()

        await client.disconnect()

        mock_session_cm.__aexit__.assert_called_once()
        mock_cm.__aexit__.assert_called_once()
        assert client._session is None
        assert client._session_cm is None
        assert client._cm is None
        assert client._read_stream is None
        assert client._write_stream is None

    async def test_context_manager(self):
        """async with should connect and disconnect."""
        client = MCPClient()
        # Mock connect and disconnect
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()

        async with client as c:
            assert c is client
            client.connect.assert_called_once()

        client.disconnect.assert_called_once()


# ====================================================================
# MCPClient list_tools tests (mocked)
# ====================================================================


class TestMCPClientListTools:
    """Tests for MCPClient.list_tools() with mocked session."""

    async def test_list_tools_not_connected(self):
        client = MCPClient()
        tools = await client.list_tools()
        assert tools == []

    async def test_list_tools_with_mock_session(self):
        client = MCPClient()
        mock_session = AsyncMock()

        # Create mock tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "read_file"
        mock_tool1.description = "Read a file"
        mock_tool1.inputSchema = {"type": "object"}

        mock_tool2 = MagicMock()
        mock_tool2.name = "write_file"
        mock_tool2.description = "Write a file"
        mock_tool2.inputSchema = {"type": "object", "properties": {"path": {"type": "string"}}}

        mock_result = MagicMock()
        mock_result.tools = [mock_tool1, mock_tool2]
        mock_session.list_tools.return_value = mock_result

        client._session = mock_session

        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "read_file"
        assert tools[0].description == "Read a file"
        assert tools[1].name == "write_file"
        assert tools[1].input_schema["properties"]["path"]["type"] == "string"

    async def test_list_tools_empty_result(self):
        client = MCPClient()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.tools = []
        mock_session.list_tools.return_value = mock_result

        client._session = mock_session

        tools = await client.list_tools()
        assert tools == []

    async def test_list_tools_session_error_returns_empty(self):
        client = MCPClient()
        mock_session = AsyncMock()
        mock_session.list_tools.side_effect = Exception("connection lost")

        client._session = mock_session

        tools = await client.list_tools()
        assert tools == []

    async def test_list_tools_as_dicts(self):
        client = MCPClient()
        mock_session = AsyncMock()

        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Web search"
        mock_tool.inputSchema = {}

        mock_result = MagicMock()
        mock_result.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_result

        client._session = mock_session

        dicts = await client.list_tools_as_dicts()
        assert len(dicts) == 1
        assert dicts[0]["name"] == "search"
        assert dicts[0]["description"] == "Web search"


# ====================================================================
# MCPClient call_tool tests (mocked)
# ====================================================================


class TestMCPClientCallTool:
    """Tests for MCPClient.call_tool() with mocked session."""

    async def test_call_tool_not_connected(self):
        client = MCPClient()
        with patch("forge_agent.mcp.client._HAS_MCP_SDK", True):
            with pytest.raises(ConnectionError, match="not connected"):
                await client.call_tool("some_tool", {})

    async def test_call_tool_success(self):
        client = MCPClient()
        mock_session = AsyncMock()

        # Create mock result
        mock_content = MagicMock()
        mock_content.text = "file contents here"

        mock_result = MagicMock()
        mock_result.content = [mock_content]
        mock_result.isError = False

        mock_session.call_tool.return_value = mock_result
        client._session = mock_session

        # Need _HAS_MCP_SDK to be True for call_tool to work
        with patch("forge_agent.mcp.client._HAS_MCP_SDK", True):
            result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})

        assert result["content"] == ["file contents here"]
        assert result["is_error"] is False
        mock_session.call_tool.assert_called_once_with(
            "read_file", arguments={"path": "/tmp/test.txt"}
        )

    async def test_call_tool_error_result(self):
        client = MCPClient()
        mock_session = AsyncMock()

        mock_content = MagicMock()
        mock_content.text = "file not found"

        mock_result = MagicMock()
        mock_result.content = [mock_content]
        mock_result.isError = True

        mock_session.call_tool.return_value = mock_result
        client._session = mock_session

        with patch("forge_agent.mcp.client._HAS_MCP_SDK", True):
            result = await client.call_tool("read_file", {"path": "/nonexistent"})

        assert result["is_error"] is True
        assert result["content"] == ["file not found"]

    async def test_call_tool_multiple_content_parts(self):
        client = MCPClient()
        mock_session = AsyncMock()

        mock_content1 = MagicMock()
        mock_content1.text = "part 1"
        mock_content2 = MagicMock()
        mock_content2.text = "part 2"

        mock_result = MagicMock()
        mock_result.content = [mock_content1, mock_content2]
        mock_result.isError = False

        mock_session.call_tool.return_value = mock_result
        client._session = mock_session

        with patch("forge_agent.mcp.client._HAS_MCP_SDK", True):
            result = await client.call_tool("multi_output", {})

        assert result["content"] == ["part 1", "part 2"]

    async def test_call_tool_session_exception(self):
        client = MCPClient()
        mock_session = AsyncMock()
        mock_session.call_tool.side_effect = Exception("timeout")
        client._session = mock_session

        with patch("forge_agent.mcp.client._HAS_MCP_SDK", True):
            with pytest.raises(RuntimeError, match="MCP tool call failed"):
                await client.call_tool("slow_tool", {})

    async def test_call_tool_no_sdk_raises_import_error(self):
        client = MCPClient()
        client._session = MagicMock()  # Pretend connected

        with patch("forge_agent.mcp.client._HAS_MCP_SDK", False):
            with pytest.raises(ImportError, match="mcp.*package.*required"):
                await client.call_tool("any_tool", {})

    async def test_call_tool_default_args(self):
        client = MCPClient()
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.content = []
        mock_result.isError = False

        mock_session.call_tool.return_value = mock_result
        client._session = mock_session

        with patch("forge_agent.mcp.client._HAS_MCP_SDK", True):
            await client.call_tool("no_args_tool")

        mock_session.call_tool.assert_called_once_with("no_args_tool", arguments={})


# ====================================================================
# MCPClient + Gateway integration tests
# ====================================================================


class TestMCPClientGatewayIntegration:
    """Tests for MCPClient working with MCPGateway."""

    async def test_client_tools_can_register_in_gateway(self):
        """Tools discovered by client can be registered in gateway."""
        from forge_agent.mcp.gateway import MCPGateway
        from forge_agent.mcp.permissions import PermissionPolicy

        client = MCPClient()
        mock_session = AsyncMock()

        mock_tool = MagicMock()
        mock_tool.name = "fs.read_file"
        mock_tool.description = "Read file"
        mock_tool.inputSchema = {}

        mock_result = MagicMock()
        mock_result.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_result
        client._session = mock_session

        tools = await client.list_tools()
        assert len(tools) == 1

        # Register in gateway with allow policy
        gateway = MCPGateway()

        async def handler(args):
            return {"result": "ok"}

        policy = PermissionPolicy().allow("fs.read_file")
        gateway.register_tool(tools[0].name, handler, policy=policy)
        assert "fs.read_file" in gateway.list_tools()

        result = await gateway.call("fs.read_file", {"path": "/test"})
        assert result == {"result": "ok"}
