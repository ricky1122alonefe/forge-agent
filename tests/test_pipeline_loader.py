"""Tests for the declarative PipelineLoader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge_agent.config.pipeline import PipelineConfig, PipelineLoader
from forge_agent.data.schema import OddsRecord

SAMPLE_CONFIG: dict = {
    "mission": {
        "mission_id": "test.pipeline",
        "name": "Test Pipeline",
    },
    "match": {
        "home": "Team A",
        "away": "Team B",
        "city": "Shanghai",
    },
    "sources": [
        {
            "source_id": "odds.mock",
            "source_type": "mock",
            "normalizer": "odds",
            "mock_payload": {
                "home": "Team A",
                "away": "Team B",
                "home_odds": 1.9,
                "draw_odds": 3.4,
                "away_odds": 3.6,
            },
            "field_map": {
                "home": "home",
                "away": "away",
                "home_odds": "home_odds",
                "draw_odds": "draw_odds",
                "away_odds": "away_odds",
            },
            "transforms": {
                "home_odds": "float",
                "draw_odds": "float",
                "away_odds": "float",
            },
        }
    ],
    "agents": [
        {
            "agent_id": "test.expert",
            "name": "Test Expert",
            "domain": "sports",
            "template": "prompt_agent",
            "config": {
                "variables": {"home": "home", "away": "away"},
                "prompt": "Analyze {home} vs {away}",
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
                "mock_response": '{"verdict": "lean_positive", "confidence": 0.8, "risk": 0.2, "evidence": ["{home} is strong"]}',
            },
        }
    ],
    "team": {
        "team_id": "test_team",
        "name": "Test Team",
        "domain": "sports",
        "agent_ids": ["test.expert"],
        "chief_id": "generic.chief",
        "mode": "parallel",
    },
}


def test_pipeline_config_from_dict() -> None:
    cfg = PipelineConfig.from_dict(SAMPLE_CONFIG)
    assert cfg.mission["mission_id"] == "test.pipeline"
    assert cfg.match["home"] == "Team A"
    assert len(cfg.sources) == 1
    assert len(cfg.agents) == 1
    assert cfg.team["team_id"] == "test_team"


def test_pipeline_loader_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(SAMPLE_CONFIG, f)

    loader = PipelineLoader.from_yaml(path)
    assert loader.config.mission["mission_id"] == "test.pipeline"


@pytest.mark.anyio
async def test_pipeline_loader_run() -> None:
    loader = PipelineLoader.from_dict(SAMPLE_CONFIG)
    board = await loader.run()

    assert board.ok
    assert len(board.agents) == 1
    report = board.agents[0]
    assert report.agent_id == "test.expert"
    assert report.verdict.value == "lean_positive"
    assert report.confidence == pytest.approx(0.8)

    chief_report = board.summary.get("chief_report")
    assert chief_report is not None
    assert chief_report["verdict"] == "lean_positive"


@pytest.mark.anyio
async def test_aggregate_odds() -> None:
    loader = PipelineLoader.from_dict(SAMPLE_CONFIG)
    records = await loader._fetch_and_normalize_sources()
    assert len(records) == 1
    assert isinstance(records[0], OddsRecord)

    payload = loader._build_payload(records)
    assert payload["home"] == "Team A"
    assert payload["away"] == "Team B"
    assert payload["home_odds"] == pytest.approx(1.9)
    assert payload["source_count"] == 1
    assert "source_evidence" in payload
