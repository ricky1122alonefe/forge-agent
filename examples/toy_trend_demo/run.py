"""Run the configurable toy trend intelligence demo.

Usage:
    cd /path/to/forge-agent
    python -m examples.toy_trend_demo.run --keyword labubu

Notes:
    - All agents default to mock_mode=true so the demo runs without API keys.
    - Set mock_mode=false in configs/trend_agents.yaml to call real LLMs.
    - Install playwright + chromium for the real Weibo scraper.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from forge_agent.builtin.chief_agent import ChiefAgent  # noqa: F401
from forge_agent.core import Mission, Team
from forge_agent.core.factory import AgentFactory
from forge_agent.core.runner import TeamRunner
from forge_agent.registry.registry import get_registry

from .agents.scraper_agent import register_tool_agent
from .tools import register_all as register_trend_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _mock_response(platform: str, verdict: str, confidence: float, risk: float) -> str:
    action_map = {
        "lean_positive": "execute",
        "lean_neutral": "watch",
        "lean_negative": "hold",
        "risk": "alert",
    }
    return json.dumps(
        {
            "verdict": verdict,
            "confidence": confidence,
            "risk": risk,
            "evidence": [
                f"{platform}: 关键词 {{keyword}} 热度持续上升。",
                f"{platform}: 用户讨论量环比增长明显。",
            ],
            "recommended_action": action_map.get(verdict, "watch"),
            "metrics": {},
        },
        ensure_ascii=False,
    )


def _build_embedded_configs() -> list[dict[str, Any]]:
    """Fallback configs used when PyYAML or the YAML file is unavailable."""
    prompt_template = (
        "你是一位潮玩趋势分析专家。请分析以下平台数据，"
        "判断关键词「{keyword}」相关的潮玩热度趋势。\n\n数据：\n{data}\n\n"
        "请输出 JSON："
        '{"verdict": "lean_positive|lean_neutral|lean_negative|risk", '
        '"confidence": 0.0-1.0, "risk": 0.0-1.0, '
        '"evidence": ["关键发现1"], '
        '"recommended_action": "execute|watch|hold|alert", '
        '"metrics": {}}'
    )
    output_schema = {
        "verdict": "str",
        "confidence": "float",
        "risk": "float",
        "evidence": "list[str]",
        "recommended_action": "str",
        "metrics": "dict",
    }
    output_mapping = {
        "verdict": "verdict",
        "confidence": "confidence",
        "risk": "risk",
        "evidence": "evidence",
        "recommended_action": "recommended_action",
        "metrics": "metrics",
    }
    return [
        {
            "agent_id": "trend.weibo",
            "name": "微博热度专家",
            "domain": "toy_trend",
            "template": "scraper_agent",
            "tags": ["social", "weibo"],
            "config": {
                "platform": "weibo",
                "tools": ["weibo.hot_search"],
                "keyword_variable": "keyword",
                "mock_mode": True,
                "mock_response": _mock_response("微博", "lean_positive", 0.82, 0.15),
                "prompt": prompt_template,
                "output_schema": output_schema,
                "output_mapping": output_mapping,
            },
        },
        {
            "agent_id": "trend.xiaohongshu",
            "name": "小红书种草专家",
            "domain": "toy_trend",
            "template": "scraper_agent",
            "tags": ["social", "xiaohongshu"],
            "config": {
                "platform": "xiaohongshu",
                "tools": ["xiaohongshu.search"],
                "keyword_variable": "keyword",
                "mock_mode": True,
                "mock_response": _mock_response("小红书", "lean_positive", 0.78, 0.20),
                "prompt": prompt_template,
                "output_schema": output_schema,
                "output_mapping": output_mapping,
            },
        },
        {
            "agent_id": "trend.dewu",
            "name": "得物价量专家",
            "domain": "toy_trend",
            "template": "scraper_agent",
            "tags": ["commerce", "dewu"],
            "config": {
                "platform": "dewu",
                "tools": ["dewu.search"],
                "keyword_variable": "keyword",
                "mock_mode": True,
                "mock_response": _mock_response("得物", "lean_neutral", 0.65, 0.35),
                "prompt": prompt_template,
                "output_schema": output_schema,
                "output_mapping": output_mapping,
            },
        },
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Toy trend intelligence demo")
    parser.add_argument("--keyword", default="labubu", help="Target keyword/IP")
    args = parser.parse_args()

    factory = AgentFactory()
    factory.register_template("scraper_agent", register_tool_agent)

    # Register social/commerce scraping tools as MCP tools so that agents can
    # invoke them declaratively via their ``tools`` config.
    register_trend_tools()

    config_path = Path(__file__).parent / "configs" / "trend_agents.yaml"
    try:
        factory.load_yaml(config_path)
        print(f"Loaded agents from {config_path}\n")
    except (ImportError, FileNotFoundError) as exc:
        print(f"YAML load failed ({exc}), using embedded dict configs.\n")
        factory.load_dicts(_build_embedded_configs())

    registry = get_registry()
    if "generic.chief" not in registry:
        raise RuntimeError("generic.chief not registered")

    team = Team(
        team_id="toy_trend_team",
        name="潮玩趋势情报小组",
        domain="toy_trend",
        agent_ids=["trend.weibo", "trend.xiaohongshu", "trend.dewu"],
        chief_id="generic.chief",
        mode="parallel",
    )

    mission = Mission(
        mission_id=f"toy_trend_{args.keyword}",
        name=f"{args.keyword} 潮玩趋势情报",
        description="基于多平台数据自动生成潮玩热度趋势报告。",
        team=team,
        payload={"keyword": args.keyword},
    )

    board = await TeamRunner().run(mission)

    print("=" * 60)
    print("Mission:", mission.name)
    print("=" * 60)
    print("\n--- 专家报告 ---")
    for report in board.agents:
        raw_data = report.raw.get("data", {})
        scraped_items = len(raw_data.get("items", []))
        data_source = "real" if raw_data.get("note") != "mock data" else "mock"
        print(
            f"\n[{report.name}] platform={report.raw.get('platform')} "
            f"verdict={report.verdict.value} confidence={report.confidence:.0%} "
            f"risk={report.risk:.0%}"
        )
        print(f"  data: {data_source}, scraped_items: {scraped_items}")
        for ev in report.evidence:
            print(f"  - {ev}")
        metrics = report.metrics
        if metrics:
            print(f"  metrics: {metrics}")

    print("\n--- Chief 汇总 ---")
    chief_report = board.summary.get("chief_report")
    if chief_report:
        print(f"verdict: {chief_report.get('verdict')}")
        print(f"confidence: {chief_report.get('confidence')}")
        print(f"risk: {chief_report.get('risk')}")
        print(f"recommended_action: {chief_report.get('recommended_action')}")
        print("evidence:")
        for ev in chief_report.get("evidence", []):
            print(f"  - {ev}")
    else:
        print("No chief report produced.")


if __name__ == "__main__":
    asyncio.run(main())
