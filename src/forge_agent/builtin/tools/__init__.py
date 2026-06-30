"""Built-in tools for forge-agent."""

from __future__ import annotations

from forge_agent.builtin.tools.social import (
    dewu_search,
    douyin_hot,
    weibo_hot_search,
    xiaohongshu_search,
)
from forge_agent.platform import Tool, get_tool_registry

__all__ = [
    "dewu_search",
    "douyin_hot",
    "register_builtin_tools",
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
