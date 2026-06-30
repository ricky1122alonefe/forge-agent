"""Tests for project TUI flows."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project import tui


class TestCreateAgent:
    def test_creates_agent_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        inputs = iter(["3", "weibo_scraper", "labubu", "weibo", "weibo.hot_search"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        registry = AgentTypeRegistry()
        tui.create_agent(tmp_path, registry)

        agent_file = tmp_path / "agents" / "weibo_scraper.yaml"
        assert agent_file.exists()
        content = agent_file.read_text(encoding="utf-8")
        assert "labubu" in content
        assert "weibo.hot_search" in content


class TestCreatePipeline:
    def test_creates_pipeline_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "weibo.yaml").write_text(
            "agents:\n  - agent_id: weibo\n",
            encoding="utf-8",
        )

        inputs = iter(["1", "y", "trend", "Trend"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        tui.create_pipeline(tmp_path)

        pipeline_file = tmp_path / "pipelines" / "trend.yaml"
        assert pipeline_file.exists()
        content = pipeline_file.read_text(encoding="utf-8")
        assert "weibo" in content
        assert "generic.chief" in content
