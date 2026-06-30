"""Tests for agent_builder utilities."""

from __future__ import annotations

import yaml

from forge_agent.project.agent_builder import (
    build_agent,
    build_agent_yaml,
    build_pipeline,
    build_pipeline_yaml,
)


class TestBuildAgent:
    def test_builds_scraper_agent(self) -> None:
        type_def = {
            "type_id": "scraper",
            "name": "Data Scraper",
            "domain": "generic",
            "template": "prompt_agent",
            "params": [
                {"name": "keyword", "type": "string", "required": True, "description": ""},
                {"name": "platform", "type": "string", "required": True, "description": ""},
                {"name": "tool", "type": "string", "required": True, "description": ""},
            ],
            "tools": ["{tool}"],
            "prompt_template": "Analyze {platform} data for {keyword}. Data: {data}",
            "output_schema": {"type": "object"},
            "output_mapping": {},
            "mock_response": '{"platform": "{platform}"}',
        }

        agent = build_agent(
            type_def,
            "weibo_scraper",
            {
                "keyword": "labubu",
                "platform": "weibo",
                "tool": "weibo.hot_search",
            },
        )

        assert agent["agent_id"] == "weibo_scraper"
        assert agent["template"] == "prompt_agent"
        assert "weibo.hot_search" in agent["config"]["tools"]
        assert "labubu" in agent["config"]["prompt"]
        assert "{data}" in agent["config"]["prompt"]
        assert "weibo" in agent["config"]["mock_response"]

    def test_build_agent_yaml_serializes(self) -> None:
        type_def = {
            "type_id": "analyzer",
            "name": "Analyzer",
            "domain": "generic",
            "template": "prompt_agent",
            "params": [],
            "prompt_template": "Analyze",
            "output_schema": {"type": "object"},
            "output_mapping": {},
        }

        text = build_agent_yaml(type_def, "my_analyzer", {})
        data = yaml.safe_load(text)

        assert "agents" in data
        assert data["agents"][0]["agent_id"] == "my_analyzer"


class TestBuildPipeline:
    def test_builds_parallel_pipeline_with_chief(self) -> None:
        pipeline = build_pipeline(
            "trend",
            "Trend Pipeline",
            ["weibo", "xiaohongshu"],
            chief_id="generic.chief",
        )

        assert pipeline["pipeline_id"] == "trend"
        assert pipeline["team"]["agent_ids"] == ["weibo", "xiaohongshu"]
        assert pipeline["team"]["chief_id"] == "generic.chief"
        assert pipeline["team"]["mode"] == "parallel"

    def test_builds_pipeline_without_chief(self) -> None:
        pipeline = build_pipeline("trend", "Trend", ["weibo"])

        assert "chief_id" not in pipeline["team"]

    def test_build_pipeline_yaml_serializes(self) -> None:
        text = build_pipeline_yaml("trend", "Trend", ["a"], chief_id="c")
        data = yaml.safe_load(text)

        assert data["pipeline_id"] == "trend"
        assert data["team"]["agent_ids"] == ["a"]
