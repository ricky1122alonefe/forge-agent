"""`forge-agent mcp` — MCP tool management: list-tools, call."""

from __future__ import annotations

import argparse
import asyncio
import json


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("mcp", help="MCP tool management")
    sub_p = p.add_subparsers(dest="mcp_cmd", required=True)

    # list-tools
    p_list = sub_p.add_parser("list-tools", help="List tools from an MCP server")
    p_list.add_argument("--stdio", nargs=argparse.REMAINDER, help="Command to start MCP server via stdio")
    p_list.add_argument("--url", help="MCP server URL (SSE transport)")
    p_list.add_argument("--prefix", default=None, help="Server prefix for tool names")
    p_list.set_defaults(func=_list_tools)

    # call
    p_call = sub_p.add_parser("call", help="Call an MCP tool")
    p_call.add_argument("tool", help="Tool name (e.g. fs.read_file)")
    p_call.add_argument("--args", "-a", default="{}", help="Tool arguments as JSON string")
    p_call.add_argument("--stdio", nargs=argparse.REMAINDER, help="Command to start MCP server via stdio")
    p_call.add_argument("--url", help="MCP server URL (SSE transport)")
    p_call.set_defaults(func=_call)

    # info
    p_info = sub_p.add_parser("info", help="Show MCP SDK status")
    p_info.set_defaults(func=_info)


def _info(args: argparse.Namespace) -> int:
    """Show MCP SDK installation status."""
    from forge_agent.mcp.client import has_mcp_sdk

    installed = has_mcp_sdk()
    print(f"MCP SDK installed: {installed}")
    if installed:
        try:
            import mcp
            print(f"MCP SDK version: {getattr(mcp, '__version__', 'unknown')}")
        except Exception:
            print("MCP SDK version: unknown")
    else:
        print("Install with: pip install 'forge-agent[mcp]'")
    return 0


def _list_tools(args: argparse.Namespace) -> int:
    return asyncio.run(_list_tools_async(args))


async def _list_tools_async(args: argparse.Namespace) -> int:
    """List tools from an MCP server."""
    from forge_agent.mcp.client import MCPClient
    from forge_agent.mcp.gateway import MCPGateway

    client = _build_client(args)
    if client is None:
        print("Error: specify --stdio <command> or --url <server_url>")
        return 1

    try:
        async with client:
            tools = await client.list_tools()
            if not tools:
                print("No tools discovered.")
                return 0

            print(f"Discovered {len(tools)} tool(s):\n")
            print(f"{'NAME':<30} {'DESCRIPTION':<50}")
            print("-" * 80)
            for t in tools:
                name = f"{args.prefix}.{t.name}" if args.prefix else t.name
                desc = (t.description or "")[:50]
                print(f"{name:<30} {desc:<50}")

            # Optionally register in gateway and show gateway view
            if args.prefix:
                gw = MCPGateway()
                registered = await gw.connect_client(client, server_prefix=args.prefix)
                print(f"\nRegistered {len(registered)} tool(s) in gateway.")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    return 0


def _call(args: argparse.Namespace) -> int:
    return asyncio.run(_call_async(args))


async def _call_async(args: argparse.Namespace) -> int:
    """Call an MCP tool."""
    from forge_agent.mcp.client import MCPClient

    client = _build_client(args)
    if client is None:
        print("Error: specify --stdio <command> or --url <server_url>")
        return 1

    try:
        tool_args = json.loads(args.args)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON for --args: {exc}")
        return 1

    # Determine the raw tool name (strip prefix if present)
    tool_name = args.tool

    try:
        async with client:
            result = await client.call_tool(tool_name, tool_args)
            if result.get("is_error"):
                print("Error:")
            for part in result.get("content", []):
                print(part)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    return 0


def _build_client(args: argparse.Namespace):
    """Build an MCPClient from CLI args."""
    from forge_agent.mcp.client import MCPClient

    if args.stdio:
        cmd = args.stdio[0]
        cmd_args = args.stdio[1:] if len(args.stdio) > 1 else []
        return MCPClient.from_stdio(cmd, cmd_args)
    elif args.url:
        return MCPClient.from_url(args.url)
    return None
