"""Tests for the SearchAgent template."""

from __future__ import annotations

from typing import Any

import pytest

from forge_agent.config.pipeline import PipelineLoader
from forge_agent.core.factory import AgentFactory
from forge_agent.core.templates.search_agent import SearchAgent, register_search_agent

SAMPLE_SEARCH_CONFIG: dict[str, Any] = {
    "agent_id": "test.search",
    "name": "Test Search Agent",
    "domain": "sports",
    "template": "search_agent",
    "config": {
        "variables": {"home": "home", "away": "away"},
        "query_template": "{home} vs {away} news",
        "search_backend": "mock",
        "mock_results": [
            {
                "title": "Preview",
                "source": "espn",
                "snippet": "Home team is strong.",
                "published_at": "2026-06-30T10:00:00Z",
            }
        ],
        "prompt": "Analyze {home} vs {away} based on {search_results}",
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


def test_register_search_agent() -> None:
    cls = register_search_agent(
        agent_id="test.register_search",
        name="Test Register Search",
        domain="sports",
        config={},
    )
    assert issubclass(cls, SearchAgent)
    assert cls.agent_id == "test.register_search"


def test_factory_creates_search_agent() -> None:
    factory = AgentFactory()
    cls = factory.from_dict(SAMPLE_SEARCH_CONFIG)
    assert issubclass(cls, SearchAgent)
    assert cls.agent_id == "test.search"


@pytest.mark.anyio()
async def test_search_agent_mock_run() -> None:
    config = {
        "mission": {"mission_id": "test.search.mission", "name": "Test Search Mission"},
        "match": {"home": "Arsenal", "away": "Liverpool"},
        "sources": [],
        "agents": [SAMPLE_SEARCH_CONFIG],
        "team": {
            "team_id": "test_search_team",
            "name": "Test Search Team",
            "domain": "sports",
            "agent_ids": ["test.search"],
            "chief_id": "generic.chief",
            "mode": "parallel",
        },
    }
    loader = PipelineLoader.from_dict(config)
    board = await loader.run()

    assert board.ok
    assert len(board.agents) == 1
    report = board.agents[0]
    assert report.agent_id == "test.search"
    assert report.verdict.value == "lean_positive"
    assert report.confidence == pytest.approx(0.8)

    search_meta = report.raw.get("search")
    assert search_meta is not None
    assert search_meta["query"] == "Arsenal vs Liverpool news"
    assert search_meta["backend"] == "mock"
    assert len(search_meta["results"]) == 1
