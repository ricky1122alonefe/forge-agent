"""MCP tools for social/commerce trend scraping.

Each tool is a thin wrapper around a headless-browser scraper.  They are
registered with the forge-agent MCP gateway so that any PromptAgent can
invoke them declaratively via its ``tools`` config.
"""

from __future__ import annotations

from typing import Any

from forge_agent.mcp.gateway import get_gateway
from forge_agent.mcp.permissions import PermissionPolicy

from ..scrapers.registry import ScraperRegistry


def register_all() -> None:
    """Register all trend scraping tools with the default MCP gateway."""
    gateway = get_gateway()
    policy = PermissionPolicy().allow("weibo.*").allow("xiaohongshu.*").allow("dewu.*")
    gateway.register_tool("weibo.hot_search", _weibo_hot_search, policy=policy)
    gateway.register_tool("xiaohongshu.search", _xiaohongshu_search, policy=policy)
    gateway.register_tool("dewu.search", _dewu_search, policy=policy)


async def _weibo_hot_search(args: dict[str, Any]) -> dict[str, Any]:
    keyword = args.get("keyword") if isinstance(args, dict) else None
    return await ScraperRegistry.scrape("weibo", keyword)


async def _xiaohongshu_search(args: dict[str, Any]) -> dict[str, Any]:
    keyword = args.get("keyword") if isinstance(args, dict) else None
    return await ScraperRegistry.scrape("xiaohongshu", keyword)


async def _dewu_search(args: dict[str, Any]) -> dict[str, Any]:
    keyword = args.get("keyword") if isinstance(args, dict) else None
    return await ScraperRegistry.scrape("dewu", keyword)
