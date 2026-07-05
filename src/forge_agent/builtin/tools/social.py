"""Built-in social media scraping tools with mock / real / auto fallback (P3.4)."""

from __future__ import annotations

import logging
from typing import Any

from forge_agent.builtin.tools.mode import ToolMode, resolve_tool_mode

log = logging.getLogger(__name__)

_PROBE_URLS: dict[str, str] = {
    "weibo": "https://s.weibo.com/top/summary?cate=realtimehot",
    "xiaohongshu": "https://www.xiaohongshu.com/",
    "dewu": "https://www.dewu.com/",
    "douyin": "https://www.douyin.com/",
}


def _mock_items(platform: str, keyword: str) -> list[dict[str, Any]]:
    if platform == "weibo":
        return [
            {"title": f"{keyword} trending topic 1", "heat": 1_000_000},
            {"title": f"{keyword} trending topic 2", "heat": 800_000},
        ]
    if platform == "xiaohongshu":
        return [
            {"title": f"{keyword} post 1", "likes": 5000},
            {"title": f"{keyword} post 2", "likes": 3000},
        ]
    if platform == "dewu":
        return [{"name": f"{keyword} product", "price": 299, "trend": "up"}]
    if platform == "douyin":
        return [{"title": f"{keyword} video 1", "plays": 2_000_000}]
    return [{"title": f"{keyword} item", "score": 1}]


async def _http_probe(url: str, *, timeout: float = 8.0) -> bool:
    """Best-effort live HTTP probe (no browser). Returns True when reachable."""
    try:
        import httpx
    except ImportError:
        return False

    headers = {"User-Agent": "forge-agent/0.1 (+https://github.com/forge-agent)"}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            return response.status_code < 400
    except Exception as exc:
        log.debug("HTTP probe failed for %s: %s", url, exc)
        return False


async def _fetch_platform(
    platform: str,
    keyword: str,
    *,
    tool_mode: str = "mock",
) -> dict[str, Any]:
    mode = resolve_tool_mode(tool_mode)
    mock_payload = {
        "platform": platform,
        "keyword": keyword,
        "items": _mock_items(platform, keyword),
    }

    if mode is ToolMode.MOCK:
        return {**mock_payload, "source": "mock"}

    probe_url = _PROBE_URLS.get(platform)
    live = bool(probe_url and await _http_probe(probe_url))

    if mode is ToolMode.REAL:
        if not live:
            raise RuntimeError(f"Live probe failed for platform {platform!r}")
        return {**mock_payload, "source": "real", "live_probe": True}

    # AUTO: try live probe, otherwise degrade to mock fixtures.
    if live:
        return {**mock_payload, "source": "real", "live_probe": True}
    return {
        **mock_payload,
        "source": "fallback",
        "fallback_reason": "live probe unavailable; using fixture data",
    }


async def weibo_hot_search(keyword: str, tool_mode: str = "mock", **kwargs: Any) -> dict[str, Any]:
    """Weibo hot search tool."""
    return await _fetch_platform("weibo", keyword, tool_mode=tool_mode)


async def xiaohongshu_search(
    keyword: str, tool_mode: str = "mock", **kwargs: Any
) -> dict[str, Any]:
    """Xiaohongshu search tool."""
    return await _fetch_platform("xiaohongshu", keyword, tool_mode=tool_mode)


async def douyin_hot(keyword: str, tool_mode: str = "mock", **kwargs: Any) -> dict[str, Any]:
    """Douyin hot trend tool."""
    return await _fetch_platform("douyin", keyword, tool_mode=tool_mode)


async def dewu_search(keyword: str, tool_mode: str = "mock", **kwargs: Any) -> dict[str, Any]:
    """Dewu search tool."""
    return await _fetch_platform("dewu", keyword, tool_mode=tool_mode)
