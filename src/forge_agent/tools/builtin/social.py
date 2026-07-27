"""Built-in social media scraping tools with mock / real / auto fallback (P3.4)."""

from __future__ import annotations

import logging
import re
from typing import Any

from forge_agent.tools.builtin.mode import ToolMode, resolve_tool_mode

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


async def _http_get_text(url: str, *, timeout: float = 12.0) -> str:
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx not installed")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) forge-agent/0.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def _parse_weibo_hot_summary_html(html: str) -> list[dict[str, Any]]:
    """
    Parse Weibo hot summary HTML into items.

    Notes:
    - Weibo markup changes; keep parser defensive and return best-effort.
    - We only extract title + heat-like score when present.
    """
    items: list[dict[str, Any]] = []

    # Common pattern: <td class="td-02"><a ...>话题</a> ...</td> and <td class="td-03">123456</td>
    row_re = re.compile(
        r'<td[^>]*class="td-02"[^>]*>.*?<a[^>]*>(?P<title>.*?)</a>.*?</td>\s*'
        r'(?:<td[^>]*class="td-03"[^>]*>(?P<heat>.*?)</td>)?',
        re.S | re.I,
    )
    for m in row_re.finditer(html):
        title_raw = re.sub(r"<.*?>", "", m.group("title") or "").strip()
        title = re.sub(r"\s+", " ", title_raw)
        if not title:
            continue

        heat_raw = re.sub(r"<.*?>", "", (m.group("heat") or "")).strip()
        heat_digits = re.sub(r"[^\d]", "", heat_raw)
        heat: int | None = int(heat_digits) if heat_digits else None

        item: dict[str, Any] = {"title": title}
        if heat is not None:
            item["heat"] = heat
        items.append(item)

    # Fallback: extract anchor titles inside td-02 even if heat failed.
    if not items:
        a_re = re.compile(r'<td[^>]*class="td-02"[^>]*>.*?<a[^>]*>(?P<title>.*?)</a>', re.S | re.I)
        for m in a_re.finditer(html):
            title_raw = re.sub(r"<.*?>", "", m.group("title") or "").strip()
            title = re.sub(r"\s+", " ", title_raw)
            if title:
                items.append({"title": title})

    # Dedup while preserving order.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for it in items:
        key = str(it.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped[:50]


async def _fetch_weibo_hot_search(*, keyword: str) -> dict[str, Any]:
    url = _PROBE_URLS["weibo"]
    html = await _http_get_text(url)
    items = _parse_weibo_hot_summary_html(html)
    if not items:
        raise RuntimeError("Failed to parse weibo hot summary HTML")
    return {
        "platform": "weibo",
        "keyword": keyword,
        "items": items,
        "source": "real",
        "url": url,
        "parsed": True,
    }


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
        if platform == "weibo":
            return await _fetch_weibo_hot_search(keyword=keyword)
        # Not implemented yet: return fixtures but make it explicit.
        return {**mock_payload, "source": "real_probe_only", "live_probe": True}

    # AUTO: try live probe, otherwise degrade to mock fixtures.
    if live:
        if platform == "weibo":
            try:
                return await _fetch_weibo_hot_search(keyword=keyword)
            except Exception as exc:
                log.debug("Weibo live fetch failed, degrading to fixtures: %s", exc)
                return {
                    **mock_payload,
                    "source": "fallback",
                    "fallback_reason": f"live fetch failed: {exc}",
                    "live_probe": True,
                }
        return {**mock_payload, "source": "real_probe_only", "live_probe": True}
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
