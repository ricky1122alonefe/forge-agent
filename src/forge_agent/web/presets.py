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


# One-click pipeline presets — creates agents (if missing) + pipeline.
PIPELINE_PRESETS: list[dict[str, Any]] = [
    {
        "preset_id": "all_platform_trend",
        "name": "三平台趋势 Demo",
        "description": "微博 + 小红书 + 得物并行分析，Chief 汇总（Mock）",
        "pipeline_id": "all_trend",
        "pipeline_name": "三平台趋势分析",
        "pipeline_description": "微博、小红书、得物并行抓取分析",
        "agent_presets": ["weibo_trend", "xhs_trend", "dewu_trend"],
        "chief_id": "generic.chief",
        "mode": "parallel",
    },
    {
        "preset_id": "multi_platform_trend",
        "name": "双平台趋势 Demo",
        "description": "微博 + 小红书并行分析，Chief 汇总决策（Mock，无需 API Key）",
        "pipeline_id": "trend",
        "pipeline_name": "双平台趋势分析",
        "pipeline_description": "微博与小红书并行抓取分析",
        "agent_presets": ["weibo_trend", "xhs_trend"],
        "chief_id": "generic.chief",
        "mode": "parallel",
    },
    {
        "preset_id": "weibo_trend_pipeline",
        "name": "微博趋势 Demo",
        "description": "单平台微博趋势分析 Pipeline",
        "pipeline_id": "weibo_trend",
        "pipeline_name": "微博趋势分析",
        "pipeline_description": "微博热搜趋势分析",
        "agent_presets": ["weibo_trend"],
        "chief_id": "generic.chief",
        "mode": "parallel",
    },
]


def get_pipeline_preset(preset_id: str) -> dict[str, Any] | None:
    for preset in PIPELINE_PRESETS:
        if preset["preset_id"] == preset_id:
            return preset
    return None


def agent_ids_for_pipeline_preset(preset: dict[str, Any]) -> list[str]:
    """Resolve default agent ids referenced by a pipeline preset."""
    agent_ids: list[str] = []
    for preset_id in preset.get("agent_presets", []):
        agent_preset = get_preset(preset_id)
        if agent_preset is None:
            continue
        agent_ids.append(agent_preset["default_agent_id"])
    return agent_ids
