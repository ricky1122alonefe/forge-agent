"""Configurable sports briefing demo.

This demo creates the same 3 sports experts as ``sports_briefing_demo.py``,
but uses ``AgentFactory`` + YAML/JSON configuration instead of hand-written
Python classes.

Run with:

    cd /path/to/forge-agent
    python -m examples.configurable_sports_demo

"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from forge_agent.core import Mission, Team
from forge_agent.core.factory import AgentFactory
from forge_agent.core.runner import TeamRunner
from forge_agent.registry.registry import get_registry


def _build_agent_configs() -> list[dict[str, Any]]:
    """Return the same 3 experts as structured configuration.

    This mirrors ``examples/configs/sports_agents.yaml`` so the demo works even
    if PyYAML is not installed.
    """
    return [
        {
            "agent_id": "sports.news",
            "name": "赛事情报专家",
            "domain": "sports",
            "template": "prompt_agent",
            "tags": ["news", "briefing"],
            "config": {
                "variables": {"home": "home", "away": "away"},
                "prompt": (
                    "你是一位足球赛事情报分析专家。\n"
                    "主队：{home}，客队：{away}。\n"
                    "请分析两队近期情报，输出 JSON：\n"
                    '{"verdict": "lean_positive|neutral|lean_negative|risk", '
                    '"confidence": 0.0-1.0, "risk": 0.0-1.0, '
                    '"evidence": ["关键情报1", "关键情报2"]}'
                ),
                "output_schema": {
                    "verdict": "str",
                    "confidence": "float",
                    "risk": "float",
                    "evidence": "list[str]",
                },
                "output_mapping": {
                    "verdict": "verdict",
                    "confidence": "confidence",
                    "risk": "risk",
                    "evidence": "evidence",
                },
                "mock_mode": True,
                "mock_response": json.dumps(
                    {
                        "verdict": "lean_positive",
                        "confidence": 0.75,
                        "risk": 0.2,
                        "evidence": [
                            "{home} 近期训练状态良好，主力阵容齐整。",
                            "{away} 上一场比赛客场取胜，士气正佳。",
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        },
        {
            "agent_id": "sports.weather",
            "name": "比赛天气专家",
            "domain": "sports",
            "template": "prompt_agent",
            "tags": ["weather", "briefing"],
            "config": {
                "variables": {"city": "city"},
                "prompt": (
                    "你是一位足球比赛天气分析专家。\n"
                    "比赛城市：{city}。\n"
                    "请分析天气对比赛的影响，输出 JSON：\n"
                    '{"verdict": "lean_positive|neutral|lean_negative|risk", '
                    '"confidence": 0.0-1.0, "risk": 0.0-1.0, '
                    '"evidence": ["天气描述"]}'
                ),
                "output_schema": {
                    "verdict": "str",
                    "confidence": "float",
                    "risk": "float",
                    "evidence": "list[str]",
                },
                "output_mapping": {
                    "verdict": "verdict",
                    "confidence": "confidence",
                    "risk": "risk",
                    "evidence": "evidence",
                },
                "mock_mode": True,
                "mock_response": json.dumps(
                    {
                        "verdict": "lean_negative",
                        "confidence": 0.8,
                        "risk": 0.4,
                        "evidence": [
                            "{city} 天气阴，30℃，风力2级，对比赛影响中等。",
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        },
        {
            "agent_id": "sports.history",
            "name": "历史交锋专家",
            "domain": "sports",
            "template": "prompt_agent",
            "tags": ["history", "briefing"],
            "config": {
                "variables": {"home": "home", "away": "away"},
                "prompt": (
                    "你是一位足球历史交锋分析专家。\n"
                    "主队：{home}，客队：{away}。\n"
                    "请分析历史交锋数据，输出 JSON：\n"
                    '{"verdict": "lean_positive|neutral|lean_negative|risk", '
                    '"confidence": 0.0-1.0, "risk": 0.0-1.0, '
                    '"evidence": ["历史交锋描述"]}'
                ),
                "output_schema": {
                    "verdict": "str",
                    "confidence": "float",
                    "risk": "float",
                    "evidence": "list[str]",
                },
                "output_mapping": {
                    "verdict": "verdict",
                    "confidence": "confidence",
                    "risk": "risk",
                    "evidence": "evidence",
                },
                "mock_mode": True,
                "mock_response": json.dumps(
                    {
                        "verdict": "lean_negative",
                        "confidence": 0.65,
                        "risk": 0.25,
                        "evidence": [
                            "历史交锋 10 场，{home} 胜 4 场。",
                            "{home} 近 3 次主场对 {away} 保持不败。",
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        },
    ]


async def main() -> None:
    factory = AgentFactory()
    config_path = Path(__file__).with_suffix("").parent / "configs" / "sports_agents.yaml"

    # Try YAML first; fall back to embedded dicts so the demo always runs.
    try:
        factory.load_yaml(config_path)
        print(f"Loaded agents from {config_path}\n")
    except ImportError:
        print("PyYAML not installed, using embedded dict configs.\n")
        factory.load_dicts(_build_agent_configs())
    except FileNotFoundError:
        print("YAML config not found, using embedded dict configs.\n")
        factory.load_dicts(_build_agent_configs())

    # Register the generic chief manually; a domain chief could also be config-driven.
    from forge_agent.builtin.chief_agent import ChiefAgent  # noqa: F401

    registry = get_registry()
    if "generic.chief" not in registry:
        raise RuntimeError("generic.chief not registered")

    team = Team(
        team_id="sports_briefing_configurable",
        name="赛事数据简报小组（配置化）",
        domain="sports",
        agent_ids=["sports.news", "sports.weather", "sports.history"],
        chief_id="generic.chief",
        mode="parallel",
    )

    mission = Mission(
        mission_id="match_briefing_configurable",
        name="海港 vs 泰山 数据简报（配置化）",
        description="通过 YAML/JSON 配置生成 agent 并执行数据简报任务。",
        team=team,
        payload={
            "home": "上海海港",
            "away": "山东泰山",
            "city": "上海",
            "date": "2026-07-01",
        },
    )

    board = await TeamRunner().run(mission)

    print("=" * 60)
    print("Mission:", mission.name)
    print("=" * 60)
    print("\n--- Member Reports (from config-driven agents) ---")
    for report in board.agents:
        print(
            f"\n[{report.name}] verdict={report.verdict.value} "
            f"confidence={report.confidence:.0%} risk={report.risk:.0%}"
        )
        for ev in report.evidence:
            print(f"  - {ev}")

    print("\n--- Chief Briefing ---")
    chief_report = board.summary.get("chief_report")
    if chief_report:
        print(f"verdict: {chief_report.get('verdict')}")
        print(f"confidence: {chief_report.get('confidence')}")
        print(f"risk: {chief_report.get('risk')}")
        print(f"summary: {chief_report.get('evidence', [''])[0]}")
    else:
        print("No chief report produced.")


if __name__ == "__main__":
    asyncio.run(main())
