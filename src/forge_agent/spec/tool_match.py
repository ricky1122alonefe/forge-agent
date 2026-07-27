"""Tool catalog metadata and requirement-based tool matching (A2.2)."""

from __future__ import annotations

from dataclasses import dataclass

from forge_agent.builtin.tools import register_builtin_tools
from forge_agent.platform.tool_registry import ToolRegistry, get_tool_registry


@dataclass(frozen=True)
class PlatformMatch:
    """A platform label matched to a registered tool."""

    label: str
    platform: str
    tool_name: str


PLATFORM_CATALOG: list[tuple[str, str, str, list[str]]] = [
    ("微博", "weibo", "weibo.hot_search", ["微博", "weibo", "热搜"]),
    ("小红书", "xiaohongshu", "xiaohongshu.search", ["小红书", "xhs", "种草"]),
    ("得物", "dewu", "dewu.search", ["得物", "dewu", "竞品", "价格"]),
    ("抖音", "douyin", "douyin.hot", ["抖音", "douyin", "热点"]),
]


def ensure_tool_catalog() -> ToolRegistry:
    """Register built-in tools with platform/keyword metadata."""
    register_builtin_tools()
    registry = get_tool_registry()
    for _label, platform, tool_name, keywords in PLATFORM_CATALOG:
        try:
            tool = registry.get(tool_name)
        except Exception:
            continue
        tool.platforms = [platform]
        tool.keywords = keywords
        if "social" not in tool.tags:
            tool.tags = [*tool.tags, "social", "trend"]
    return registry


def match_platforms(requirement: str) -> list[PlatformMatch]:
    """Return all platform tools matching a requirement (A2.2)."""
    registry = ensure_tool_catalog()
    available = set(registry.list_names())
    req_lower = requirement.lower()
    matches: list[PlatformMatch] = []

    for label, platform, tool_name, keywords in PLATFORM_CATALOG:
        if tool_name not in available:
            continue
        if label in requirement or any(k.lower() in req_lower for k in keywords):
            matches.append(PlatformMatch(label=label, platform=platform, tool_name=tool_name))

    if (
        not matches
        and ("微博" in requirement or "weibo" in req_lower)
        and "weibo.hot_search" in available
    ):
        matches.append(PlatformMatch(label="微博", platform="weibo", tool_name="weibo.hot_search"))
    return matches


def primary_platform(requirement: str) -> PlatformMatch | None:
    matches = match_platforms(requirement)
    return matches[0] if matches else None


def list_tool_catalog() -> list[dict[str, object]]:
    """Serialize tool metadata for APIs and generators."""
    registry = ensure_tool_catalog()
    items: list[dict[str, object]] = []
    for tool in registry.list():
        items.append(
            {
                "name": tool.name,
                "description": tool.description,
                "platforms": tool.platforms,
                "keywords": tool.keywords,
                "tags": tool.tags,
            }
        )
    return items
