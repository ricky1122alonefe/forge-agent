"""Multi-source odds normalization demo.

Shows how two different raw data formats (English nested JSON vs Chinese flat
dict) can be normalized into the same OddsRecord and fed into a configurable
agent.

Run with:

    cd /path/to/forge-agent
    python -m examples.multi_source_odds_demo

"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import yaml

from forge_agent.builtin.chief_agent import ChiefAgent  # noqa: F401
from forge_agent.core import Mission, Team
from forge_agent.core.factory import AgentFactory
from forge_agent.core.runner import TeamRunner
from forge_agent.data.normalizer import Normalizer, NormalizerConfig
from forge_agent.data.schema import OddsRecord
from forge_agent.data.source import DataSource, DataSourceConfig


def _build_source_configs() -> list[dict[str, Any]]:
    """Embedded config mirror of ``examples/configs/odds_sources.yaml``."""
    return [
        {
            "source_id": "odds.site_a",
            "name": "站点 A 赔率",
            "source_type": "mock",
            "normalizer": "odds",
            "mock_payload": {
                "match": {
                    "home_team": "Arsenal",
                    "away_team": "Liverpool",
                },
                "odds": {
                    "home_win": "2.10",
                    "draw": "3.40",
                    "away_win": "3.20",
                },
            },
            "field_map": {
                "home": "match.home_team",
                "away": "match.away_team",
                "home_odds": "odds.home_win",
                "draw_odds": "odds.draw",
                "away_odds": "odds.away_win",
            },
            "transforms": {
                "home_odds": "float",
                "draw_odds": "float",
                "away_odds": "float",
            },
        },
        {
            "source_id": "odds.site_b",
            "name": "站点 B 赔率",
            "source_type": "mock",
            "normalizer": "odds",
            "mock_payload": {
                "主队": "阿森纳",
                "客队": "利物浦",
                "主胜": 2.08,
                "平局": 3.42,
                "客胜": 3.25,
            },
            "field_map": {
                "home": "主队",
                "away": "客队",
                "home_odds": "主胜",
                "draw_odds": "平局",
                "away_odds": "客胜",
            },
            "transforms": {
                "home_odds": "float",
                "draw_odds": "float",
                "away_odds": "float",
            },
        },
    ]


def load_source_configs(path: Path) -> list[dict[str, Any]]:
    """Load source definitions from YAML or fall back to embedded dicts."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("sources", []) if isinstance(data, dict) else data
    except (ImportError, FileNotFoundError):
        return _build_source_configs()


async def fetch_and_normalize(source_cfg: dict[str, Any]) -> OddsRecord:
    """Fetch raw data from one source and normalize it."""
    source = DataSource(DataSourceConfig(**source_cfg))
    raw = await source.fetch()

    normalizer_cfg = NormalizerConfig(
        schema=source_cfg.get("normalizer", "odds"),
        field_map=source_cfg.get("field_map", {}),
        transforms=source_cfg.get("transforms", {}),
    )
    normalizer = Normalizer(normalizer_cfg)
    record = normalizer.normalize(source, raw)
    if not isinstance(record, OddsRecord):
        raise TypeError(f"Expected OddsRecord, got {type(record)}")
    return record


async def main() -> None:
    config_path = Path(__file__).with_suffix("").parent / "configs" / "odds_sources.yaml"
    source_configs = load_source_configs(config_path)

    print("=" * 60)
    print("Multi-Source Odds Normalization Demo")
    print("=" * 60)

    records = []
    for cfg in source_configs:
        record = await fetch_and_normalize(cfg)
        records.append(record)
        print(f"\n--- {record.source} ---")
        print("Raw keys:", list(record.raw.keys()))
        print(
            "Normalized:",
            {
                "home": record.home,
                "away": record.away,
                "home_odds": record.home_odds,
                "draw_odds": record.draw_odds,
                "away_odds": record.away_odds,
            },
        )
        print("Evidence:")
        for ev in record.to_evidence():
            print(f"  - {ev}")

    # Feed normalized records into a config-driven odds agent.
    factory = AgentFactory()
    factory.from_dict(
        {
            "agent_id": "sports.odds",
            "name": "赔率分析专家",
            "domain": "sports",
            "template": "prompt_agent",
            "tags": ["odds", "briefing"],
            "config": {
                "variables": {
                    "home": "home",
                    "away": "away",
                    "home_odds": "home_odds",
                    "away_odds": "away_odds",
                    "draw_odds": "draw_odds",
                    "sources": "sources",
                },
                "mock_mode": True,
                "mock_response": json.dumps(
                    {
                        "verdict": "lean_negative",
                        "confidence": 0.72,
                        "risk": 0.35,
                        "evidence": [
                            "来源 {sources}，{home} 胜赔 {home_odds}，平局 {draw_odds}，{away} 胜赔 {away_odds}",
                            "赔率显示客队赔付有一定压力",
                        ],
                    },
                    ensure_ascii=False,
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
            },
        }
    )

    # Build an aggregated payload from all records.
    aggregated: dict[str, Any] = {
        "home": records[0].home,
        "away": records[0].away,
        "home_odds": records[0].home_odds,
        "draw_odds": records[0].draw_odds,
        "away_odds": records[0].away_odds,
        "sources": ", ".join(r.source for r in records),
    }

    team = Team(
        team_id="odds_analysis",
        name="赔率分析小组",
        domain="sports",
        agent_ids=["sports.odds"],
        chief_id="generic.chief",
        mode="parallel",
    )
    mission = Mission(
        mission_id="odds_multi_source_demo",
        name="多源赔率分析",
        team=team,
        payload=aggregated,
    )

    board = await TeamRunner().run(mission)

    print("\n--- Agent Report ---")
    for report in board.agents:
        print(
            f"[{report.name}] verdict={report.verdict.value} "
            f"confidence={report.confidence:.0%} risk={report.risk:.0%}"
        )
        for ev in report.evidence:
            print(f"  - {ev}")

    chief_report = board.summary.get("chief_report")
    if chief_report:
        print("\n--- Chief Briefing ---")
        print(f"verdict: {chief_report.get('verdict')}")
        print(f"confidence: {chief_report.get('confidence')}")
        print(f"risk: {chief_report.get('risk')}")


if __name__ == "__main__":
    asyncio.run(main())
