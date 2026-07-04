"""Tests for web UI data helpers."""

from __future__ import annotations

from pathlib import Path

import yaml

from forge_agent.project.agent_builder import build_agent_yaml, build_pipeline_yaml
from forge_agent.web.data import (
    collect_payload_fields,
    extract_chief_report,
    format_trace_timeline,
    get_agent_config,
    get_pipeline_run_plan,
    infer_run_mock_mode,
    list_agents,
    summarize_project_mock_mode,
)
from forge_agent.web.presets import (
    agent_ids_for_pipeline_preset,
    get_pipeline_preset,
    get_preset,
    template_label,
)


def _write_agent(project: Path, agent_id: str, variables: dict | None = None) -> None:
    type_def = {
        "type_id": "scraper",
        "name": "Scraper",
        "domain": "generic",
        "template": "prompt_agent",
        "params": [
            {"name": "keyword", "type": "string", "required": True, "description": ""},
            {"name": "platform", "type": "string", "required": True, "description": ""},
            {"name": "tool", "type": "string", "required": True, "description": ""},
        ],
        "tools": ["{tool}"],
        "prompt_template": "Analyze {keyword} on {platform}",
        "output_schema": {"verdict": "str"},
        "output_mapping": {"verdict": "verdict"},
        "mock_response": '{"verdict": "lean_positive"}',
    }
    text = build_agent_yaml(
        type_def,
        agent_id,
        {"keyword": "labubu", "platform": "weibo", "tool": "weibo.hot_search"},
    )
    (project / "agents" / f"{agent_id}.yaml").write_text(text, encoding="utf-8")
    if variables:
        data = yaml.safe_load(text)
        data["agents"][0]["config"]["variables"] = variables
        (project / "agents" / f"{agent_id}.yaml").write_text(
            yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
        )


class TestWebDataHelpers:
    def test_template_label(self) -> None:
        assert template_label("scraper", "Data Scraper") == "数据抓取"
        assert template_label("custom", "My Type") == "My Type"

    def test_get_agent_config(self, tmp_path: Path) -> None:
        project = tmp_path / "demo"
        (project / "agents").mkdir(parents=True)
        _write_agent(project, "weibo_analyst", {"keyword": "keyword", "platform": "platform"})

        config = get_agent_config(project, "weibo_analyst")
        assert config["mock_mode"] is True
        assert "labubu" in config["prompt"]
        assert "weibo.hot_search" in config["tools"]

    def test_collect_payload_fields(self, tmp_path: Path) -> None:
        project = tmp_path / "demo"
        (project / "agents").mkdir(parents=True)
        (project / "pipelines").mkdir(parents=True)
        _write_agent(project, "a1", {"keyword": "keyword"})
        _write_agent(project, "a2", {"keyword": "keyword", "platform": "platform"})

        pipeline_yaml = build_pipeline_yaml(
            "trend", "Trend", ["a1", "a2"], chief_id="generic.chief"
        )
        (project / "pipelines" / "trend.yaml").write_text(pipeline_yaml, encoding="utf-8")

        fields = collect_payload_fields(project, "trend")
        names = [f["name"] for f in fields]
        assert names == ["keyword"]
        assert fields[0]["label"] == "关键词"
        assert fields[0]["default"] == "labubu"

    def test_collect_payload_fields_legacy_variables(self, tmp_path: Path) -> None:
        project = tmp_path / "demo"
        (project / "agents").mkdir(parents=True)
        (project / "pipelines").mkdir(parents=True)
        _write_agent(
            project,
            "legacy",
            {"keyword": "keyword", "platform": "platform", "tool": "tool"},
        )
        pipeline_yaml = build_pipeline_yaml("solo", "Solo", ["legacy"], chief_id="generic.chief")
        (project / "pipelines" / "solo.yaml").write_text(pipeline_yaml, encoding="utf-8")

        fields = collect_payload_fields(project, "solo")
        assert [f["name"] for f in fields] == ["keyword"]

    def test_extract_chief_report(self) -> None:
        summary = {"chief_report": {"verdict": "lean_positive", "evidence": ["ok"]}}
        report = extract_chief_report(summary)
        assert report is not None
        assert report["verdict"] == "lean_positive"

    def test_get_preset(self) -> None:
        preset = get_preset("weibo_trend")
        assert preset is not None
        assert preset["agent_type"] == "scraper"

    def test_get_pipeline_preset(self) -> None:
        preset = get_pipeline_preset("multi_platform_trend")
        assert preset is not None
        assert preset["pipeline_id"] == "trend"

    def test_agent_ids_for_pipeline_preset(self) -> None:
        preset = get_pipeline_preset("multi_platform_trend")
        assert preset is not None
        ids = agent_ids_for_pipeline_preset(preset)
        assert ids == ["weibo_analyst", "xhs_analyst"]

        all_preset = get_pipeline_preset("all_platform_trend")
        assert all_preset is not None
        assert agent_ids_for_pipeline_preset(all_preset) == [
            "weibo_analyst",
            "xhs_analyst",
            "dewu_analyst",
        ]

    def test_list_agents(self, tmp_path: Path) -> None:
        project = tmp_path / "demo"
        (project / "agents").mkdir(parents=True)
        _write_agent(project, "x1")
        agents = list_agents(project)
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "x1"

    def test_summarize_project_mock_mode(self, tmp_path: Path) -> None:
        project = tmp_path / "demo"
        (project / "agents").mkdir(parents=True)
        _write_agent(project, "a1")
        summary = summarize_project_mock_mode(project)
        assert summary["total"] == 1
        assert summary["all_mock"] is True
        assert summary["any_mock"] is True

    def test_get_pipeline_run_plan(self, tmp_path: Path) -> None:
        project = tmp_path / "demo"
        (project / "agents").mkdir(parents=True)
        (project / "pipelines").mkdir(parents=True)
        _write_agent(project, "a1")
        pipeline_yaml = build_pipeline_yaml("trend", "Trend", ["a1"], chief_id="generic.chief")
        (project / "pipelines" / "trend.yaml").write_text(pipeline_yaml, encoding="utf-8")

        plan = get_pipeline_run_plan(project, "trend")
        assert len(plan) == 2
        assert plan[0]["kind"] == "agent"
        assert plan[1]["kind"] == "chief"

    def test_infer_run_mock_mode(self) -> None:
        reports = [{"raw": {"decision": {"config": {"mock_mode": True}}}}]
        assert infer_run_mock_mode(reports) is True
        reports.append({"raw": {"decision": {"config": {"mock_mode": False}}}})
        assert infer_run_mock_mode(reports) is False

    def test_format_trace_timeline(self) -> None:
        trace = {
            "spans": [
                {
                    "name": "team.trend",
                    "span_type": "pipeline",
                    "duration_ms": 12.5,
                    "status": "ok",
                },
                {
                    "name": "weibo_scraper.run",
                    "span_type": "agent",
                    "duration_ms": 4.2,
                    "status": "ok",
                    "attributes": {"agent_id": "weibo_scraper"},
                },
                {
                    "name": "weibo_scraper.decide",
                    "span_type": "decide",
                    "duration_ms": 1.0,
                    "status": "ok",
                },
            ]
        }
        timeline = format_trace_timeline(trace)
        names = [step["name"] for step in timeline]
        assert "team.trend" in names
        assert "weibo_scraper" in names
        assert "weibo_scraper.decide" not in names
