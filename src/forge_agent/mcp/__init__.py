"""MCP (Model Context Protocol) integration — gateway + permissions.

v0.3+ goal: this package becomes the single point of access for ALL
external capabilities (LLM, search, DB, file). For v0.1 we ship the
permission scaffolding only; wire the actual `mcp` SDK in v0.3.
"""

from __future__ import annotations

from forge_agent.mcp.client import MCPClient, ToolInfo, has_mcp_sdk
from forge_agent.mcp.gateway import MCPGateway, get_gateway, reset_gateway
from forge_agent.mcp.permissions import PermissionPolicy, PermissionRule

__all__ = [
    "MCPClient",
    "MCPGateway",
    "PermissionPolicy",
    "PermissionRule",
    "ToolInfo",
    "get_gateway",
    "has_mcp_sdk",
    "reset_gateway",
]
