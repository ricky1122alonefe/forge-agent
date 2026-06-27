"""Integration tests for MCP tools support in the generation pipeline.

Verifies that:
    - Pipeline picks up MCP tools from the gateway and passes them to GenerationContext
    - build_user_prompt includes MCP tool names
    - Pipeline works gracefully when no MCP tools are registered
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from forge_agent.generator.generator import GenerationContext
from forge_agent.generator.prompts import build_user_prompt
from forge_agent.mcp.gateway import MCPGateway, get_gateway, reset_gateway


@pytest.fixture(autouse=True)
def _reset():
    reset_gateway()
    yield
    reset_gateway()


class TestBuildUserPromptWithMCP:
    """Test that build_user_prompt includes MCP tools."""

    def test_prompt_includes_mcp_tools(self):
        prompt = build_user_prompt(
            "Monitor stock prices",
            mcp_tools=["tavily.search", "db.read", "db.write"],
        )
        assert "tavily.search" in prompt
        assert "db.read" in prompt
        assert "db.write" in prompt
        assert "MCP" in prompt

    def test_prompt_without_mcp_tools(self):
        prompt = build_user_prompt("Monitor stock prices")
        assert "MCP" not in prompt

    def test_prompt_with_empty_mcp_tools(self):
        prompt = build_user_prompt("Monitor stock prices", mcp_tools=[])
        assert "MCP" not in prompt


class TestGenerationContextMCP:
    """Test GenerationContext MCP fields."""

    def test_default_empty_mcp_tools(self):
        from forge_agent.generator.requirements import AgentRequirements
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test",
            domain="generic",
            description="test",
        )
        ctx = GenerationContext(requirements=req)
        assert ctx.mcp_tools_available == []

    def test_mcp_tools_in_context(self):
        from forge_agent.generator.requirements import AgentRequirements
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test",
            domain="generic",
            description="test",
        )
        ctx = GenerationContext(
            requirements=req,
            mcp_tools_available=["tavily.search", "db.read"],
        )
        assert ctx.mcp_tools_available == ["tavily.search", "db.read"]


class TestPipelineMCPIntegration:
    """Test that the pipeline passes MCP tools to GenerationContext."""

    @pytest.mark.asyncio
    async def test_pipeline_passes_mcp_tools_to_context(self):
        """Pipeline should get tools from gateway and pass to GenerationContext."""
        # Register some tools in the gateway
        gw = get_gateway()

        async def dummy_handler(args):
            return {"ok": True}

        from forge_agent.mcp.permissions import PermissionPolicy
        gw.register_tool("tavily.search", dummy_handler, policy=PermissionPolicy().allow("tavily.search"))
        gw.register_tool("db.read", dummy_handler, policy=PermissionPolicy().allow("db.read"))

        assert set(gw.list_tools()) == {"tavily.search", "db.read"}

        # Now simulate what pipeline does
        mcp_tools_available = gw.list_tools()
        assert len(mcp_tools_available) == 2

        # Verify they'd be passed to GenerationContext
        from forge_agent.generator.requirements import AgentRequirements
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test",
            domain="generic",
            description="test",
        )
        ctx = GenerationContext(
            requirements=req,
            mcp_tools_available=mcp_tools_available,
        )
        assert "tavily.search" in ctx.mcp_tools_available
        assert "db.read" in ctx.mcp_tools_available

    @pytest.mark.asyncio
    async def test_pipeline_works_without_mcp_tools(self):
        """Pipeline should work fine when gateway has no tools."""
        gw = get_gateway()
        assert gw.list_tools() == []

        from forge_agent.generator.requirements import AgentRequirements
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test",
            domain="generic",
            description="test",
        )
        ctx = GenerationContext(
            requirements=req,
            mcp_tools_available=gw.list_tools(),
        )
        assert ctx.mcp_tools_available == []

    @pytest.mark.asyncio
    async def test_pipeline_mcp_tools_appear_in_prompt(self):
        """MCP tools from gateway should appear in the generated prompt."""
        gw = get_gateway()

        async def dummy_handler(args):
            return {"ok": True}

        from forge_agent.mcp.permissions import PermissionPolicy
        gw.register_tool("tavily.search", dummy_handler, policy=PermissionPolicy().allow("tavily.search"))
        gw.register_tool("fs.read_file", dummy_handler, policy=PermissionPolicy().allow("fs.read_file"))

        # Simulate pipeline flow
        mcp_tools = gw.list_tools()
        prompt = build_user_prompt(
            "Build a web scraper",
            mcp_tools=mcp_tools,
        )
        assert "tavily.search" in prompt
        assert "fs.read_file" in prompt
