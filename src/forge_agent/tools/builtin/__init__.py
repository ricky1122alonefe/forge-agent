"""Built-in tools for forge-agent."""

from __future__ import annotations

from forge_agent.platform.tool import Tool
from forge_agent.platform.tool_registry import get_tool_registry
from forge_agent.tools.builtin.mode import ToolMode, resolve_tool_mode
from forge_agent.tools.builtin.social import (
    dewu_search,
    douyin_hot,
    weibo_hot_search,
    xiaohongshu_search,
)

__all__ = [
    "ToolMode",
    "dewu_search",
    "douyin_hot",
    "register_builtin_tools",
    "resolve_tool_mode",
    "weibo_hot_search",
    "xiaohongshu_search",
]


def register_builtin_tools() -> None:
    """Register all built-in tools into the global tool registry."""
    registry = get_tool_registry()
    registry.register(
        Tool(
            name="weibo.hot_search",
            description="Fetch Weibo hot search trends for a keyword.",
            handler=weibo_hot_search,
        )
    )
    registry.register(
        Tool(
            name="xiaohongshu.search",
            description="Search Xiaohongshu (Little Red Book) posts for a keyword.",
            handler=xiaohongshu_search,
        )
    )
    registry.register(
        Tool(
            name="dewu.search",
            description="Search Dewu (Poizon) product/trend data for a keyword.",
            handler=dewu_search,
        )
    )
    registry.register(
        Tool(
            name="douyin.hot",
            description="Fetch Douyin hot trends for a keyword.",
            handler=douyin_hot,
        )
    )
