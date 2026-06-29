"""Tests for `forge-agent mcp` CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from forge_agent.cli.cmd_mcp import _build_client, _info
from forge_agent.mcp.client import MCPClient, ToolInfo


class TestMCPInfoCommand:
    """Test the `mcp info` subcommand."""

    def test_info_with_sdk_installed(self, capsys):
        """info should show SDK status when installed."""
        args = MagicMock()
        with (
            patch("forge_agent.mcp.client.has_mcp_sdk", return_value=True),
            patch.dict("sys.modules", {"mcp": MagicMock(__version__="1.0.0")}),
        ):
            result = _info(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "MCP SDK installed: True" in captured.out

    def test_info_without_sdk(self, capsys):
        """info should show install instructions when SDK missing."""
        args = MagicMock()
        with patch("forge_agent.mcp.client.has_mcp_sdk", return_value=False):
            result = _info(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "MCP SDK installed: False" in captured.out
        assert "pip install" in captured.out


class TestMCPBuildClient:
    """Test _build_client helper."""

    def test_build_client_stdio(self):
        """Should create stdio client from --stdio args."""
        args = MagicMock()
        args.stdio = ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        args.url = None

        client = _build_client(args)
        assert client is not None
        assert client.command == "npx"
        assert client.args == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

    def test_build_client_url(self):
        """Should create SSE client from --url arg."""
        args = MagicMock()
        args.stdio = None
        args.url = "http://localhost:8080/sse"

        client = _build_client(args)
        assert client is not None
        assert client.server_url == "http://localhost:8080/sse"

    def test_build_client_none(self):
        """Should return None when no transport specified."""
        args = MagicMock()
        args.stdio = None
        args.url = None

        client = _build_client(args)
        assert client is None


class TestMCPListTools:
    """Test the `mcp list-tools` subcommand."""

    @pytest.mark.asyncio
    async def test_list_tools_no_transport(self, capsys):
        """Should error when no transport specified."""
        args = MagicMock()
        args.stdio = None
        args.url = None
        args.prefix = None

        result = await _list_tools_async_direct(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    @pytest.mark.asyncio
    async def test_list_tools_with_mock_client(self, capsys):
        """Should list tools from mocked client."""
        args = MagicMock()
        args.stdio = ["mock"]
        args.url = None
        args.prefix = "fs"

        mock_client = _make_mock_client(
            [
                ToolInfo(name="read_file", description="Read a file"),
                ToolInfo(name="write_file", description="Write a file"),
            ]
        )

        with patch("forge_agent.cli.cmd_mcp._build_client", return_value=mock_client):
            result = await _list_tools_async_direct(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Discovered 2 tool(s)" in captured.out
        assert "fs.read_file" in captured.out
        assert "fs.write_file" in captured.out


class TestMCPCallTool:
    """Test the `mcp call` subcommand."""

    @pytest.mark.asyncio
    async def test_call_no_transport(self, capsys):
        """Should error when no transport specified."""
        args = MagicMock()
        args.stdio = None
        args.url = None
        args.tool = "read_file"
        args.args = "{}"

        result = await _call_async_direct(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_call_invalid_json(self, capsys):
        """Should error on invalid JSON args."""
        args = MagicMock()
        args.stdio = ["mock"]
        args.url = None
        args.tool = "read_file"
        args.args = "not json"

        mock_client = _make_mock_client()
        with patch("forge_agent.cli.cmd_mcp._build_client", return_value=mock_client):
            result = await _call_async_direct(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid JSON" in captured.out

    @pytest.mark.asyncio
    async def test_call_success(self, capsys):
        """Should call tool and print result."""
        args = MagicMock()
        args.stdio = ["mock"]
        args.url = None
        args.tool = "read_file"
        args.args = '{"path": "/tmp/test.txt"}'

        mock_client = _make_mock_client(
            call_results={"read_file": {"content": ["Hello World"], "is_error": False}}
        )

        with patch("forge_agent.cli.cmd_mcp._build_client", return_value=mock_client):
            result = await _call_async_direct(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Hello World" in captured.out


# ------------------------------------------------------------------ Helpers


def _make_mock_client(
    tools: list[ToolInfo] | None = None,
    call_results: dict[str, dict] | None = None,
) -> MCPClient:
    """Create a mocked MCPClient."""
    client = MCPClient.__new__(MCPClient)
    client.server_url = None
    client.command = "mock"
    client.args = []
    client.env = None
    client._session = MagicMock()
    client._read_stream = None
    client._write_stream = None
    client._cm = None
    client._session_cm = None

    tools = tools or [ToolInfo(name="mock_tool", description="Mock")]
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

    async def mock_aenter():
        await mock_connect()
        return client

    async def mock_aexit(*exc):
        await mock_disconnect()

    client.list_tools = mock_list_tools  # type: ignore
    client.call_tool = mock_call_tool  # type: ignore
    client.connect = mock_connect  # type: ignore
    client.disconnect = mock_disconnect  # type: ignore
    client.__aenter__ = mock_aenter  # type: ignore
    client.__aexit__ = mock_aexit  # type: ignore

    return client


async def _list_tools_async_direct(args):
    """Direct call to the async implementation."""
    from forge_agent.cli.cmd_mcp import _list_tools_async

    return await _list_tools_async(args)


async def _call_async_direct(args):
    """Direct call to the async implementation."""
    from forge_agent.cli.cmd_mcp import _call_async

    return await _call_async(args)
