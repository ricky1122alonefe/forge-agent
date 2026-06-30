"""Tests for ToolRegistry."""

from __future__ import annotations

import pytest

from forge_agent.platform import Tool, ToolNotFoundError, reset_tool_registry


async def _dummy_handler(keyword: str) -> dict:
    return {"keyword": keyword}


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        registry = reset_tool_registry()
        registry.register(Tool(name="test.tool", description="A test tool", handler=_dummy_handler))

        tool = registry.get("test.tool")
        assert tool.name == "test.tool"

    def test_get_missing_raises(self) -> None:
        registry = reset_tool_registry()
        with pytest.raises(ToolNotFoundError):
            registry.get("missing")

    def test_list_names(self) -> None:
        registry = reset_tool_registry()
        registry.register(Tool(name="a.tool", description="", handler=_dummy_handler))
        registry.register(Tool(name="b.tool", description="", handler=_dummy_handler))

        assert registry.list_names() == ["a.tool", "b.tool"]
