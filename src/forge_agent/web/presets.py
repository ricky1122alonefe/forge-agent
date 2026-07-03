"""Agent template labels and one-click presets for the web UI."""

from __future__ import annotations

from typing import Any

# User-facing labels for built-in agent type templates (P1.3).
AGENT_TEMPLATE_LABELS: dict[str, str] = {
    "scraper": "数据抓取",
    "analyzer": "数据分析",
    "chief": "决策汇总",
}


def template_label(type_id: str, fallback_name: str = "") -> str:
    """Return a user-friendly label for an agent type template."""
    if type_id in AGENT_TEMPLATE_LABELS:
        return AGENT_TEMPLATE_LABELS[type_id]
    return fallback_name or type_id


# One-click agent presets (P1.8).
AGENT_PRESETS: list[dict[str, Any]] = [
    {
        "preset_id": "weibo_trend",
        "name": "微博趋势分析",
        "description": "抓取微博热搜并分析关键词趋势",
        "agent_type": "scraper",
        "default_agent_id": "weibo_analyst",
        "params": {
            "keyword": "labubu",
            "platform": "weibo",
            "tool": "weibo.hot_search",
        },
    },
    {
        "preset_id": "xhs_trend",
        "name": "小红书趋势分析",
        "description": "搜索小红书笔记并分析种草热度",
        "agent_type": "scraper",
        "default_agent_id": "xhs_analyst",
        "params": {
            "keyword": "labubu",
            "platform": "xiaohongshu",
            "tool": "xiaohongshu.search",
        },
    },
    {
        "preset_id": "dewu_trend",
        "name": "得物趋势分析",
        "description": "搜索得物商品并分析价格/热度趋势",
        "agent_type": "scraper",
        "default_agent_id": "dewu_analyst",
        "params": {
            "keyword": "labubu",
            "platform": "dewu",
            "tool": "dewu.search",
        },
    },
]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    for preset in AGENT_PRESETS:
        if preset["preset_id"] == preset_id:
            return preset
    return None
