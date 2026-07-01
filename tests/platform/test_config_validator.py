"""Tests for forge_agent.platform.config_validator."""

from __future__ import annotations

import pytest
import yaml

from forge_agent.exceptions import ConfigValidationError
from forge_agent.platform import ConfigValidator


@pytest.fixture
def project(tmp_path):
    """Create a minimal forge-agent project layout."""
    root = tmp_path / "demo"
    (root / "agents").mkdir(parents=True)
    (root / "pipelines").mkdir(parents=True)
    return root


def _write_agent(project, agent_id, template="prompt_agent", tools=None, extra=None):
    data = {
        "agents": [
            {
                "agent_id": agent_id,
                "name": agent_id,
                "template": template,
                "config": {
                    "prompt": "Hello {name}",
                    "output_schema": {"verdict": "str"},
                    "output_mapping": {"verdict": "verdict"},
                },
            }
        ]
    }
    if tools:
        data["agents"][0]["config"]["tools"] = tools
    if extra:
        data["agents"][0]["config"].update(extra)
    path = project / "agents" / f"{agent_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def _write_pipeline(project, pipeline_id, agent_ids, chief_id=None, mode="parallel"):
    data = {
        "pipeline_id": pipeline_id,
        "name": pipeline_id,
        "team": {
            "team_id": f"{pipeline_id}_team",
            "name": f"{pipeline_id} team",
            "agent_ids": agent_ids,
            "mode": mode,
        },
    }
    if chief_id:
        data["team"]["chief_id"] = chief_id
    path = project / "pipelines" / f"{pipeline_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_valid_project_passes(project):
    _write_agent(project, "agent.one")
    _write_pipeline(project, "main", ["agent.one"])

    ConfigValidator(project).validate("main")  # should not raise


def test_missing_agent_reference_fails(project):
    _write_agent(project, "agent.one")
    _write_pipeline(project, "main", ["agent.one", "agent.missing"])

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate("main")
    assert "agent.missing" in str(exc_info.value)


def test_unknown_template_fails(project):
    _write_agent(project, "agent.one", template="unknown_template")
    _write_pipeline(project, "main", ["agent.one"])

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate("main")
    assert "unknown_template" in str(exc_info.value)


def test_missing_required_agent_field_fails(project):
    data = {"agents": [{"template": "prompt_agent", "config": {}}]}
    (project / "agents" / "bad.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate_agents_only()
    assert "agent_id" in str(exc_info.value)


def test_unknown_tool_fails(project):
    _write_agent(project, "agent.one", tools=["weibo.hot_search", "not.a.tool"])
    _write_pipeline(project, "main", ["agent.one"])

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate("main")
    assert "not.a.tool" in str(exc_info.value)


def test_inline_agent_in_pipeline(project):
    _write_pipeline(project, "main", ["inline.agent"])
    pipeline_path = project / "pipelines" / "main.yaml"
    raw = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))
    raw["agents"] = [
        {
            "agent_id": "inline.agent",
            "name": "Inline Agent",
            "template": "prompt_agent",
            "config": {
                "prompt": "Hello",
                "output_schema": {"verdict": "str"},
                "output_mapping": {"verdict": "verdict"},
            },
        }
    ]
    pipeline_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    ConfigValidator(project).validate("main")  # should not raise


def test_chief_must_be_defined(project):
    _write_agent(project, "agent.one")
    _write_pipeline(project, "main", ["agent.one"], chief_id="generic.chief")

    # generic.chief is a built-in agent, so it is valid even without being defined locally.
    ConfigValidator(project).validate("main")


def test_unknown_chief_fails(project):
    _write_agent(project, "agent.one")
    _write_pipeline(project, "main", ["agent.one"], chief_id="no.such.chief")

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate("main")
    assert "no.such.chief" in str(exc_info.value)


def test_invalid_team_mode_fails(project):
    _write_agent(project, "agent.one")
    _write_pipeline(project, "main", ["agent.one"], mode="concurrent")

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate("main")
    assert "concurrent" in str(exc_info.value)


def test_duplicate_agent_id_fails(project):
    _write_agent(project, "agent.one")
    # Write the same agent_id under a different file name to trigger the duplicate check.
    data = {
        "agents": [
            {
                "agent_id": "agent.one",
                "name": "agent one again",
                "template": "prompt_agent",
                "config": {
                    "prompt": "Hello",
                    "output_schema": {"verdict": "str"},
                    "output_mapping": {"verdict": "verdict"},
                },
            }
        ]
    }
    (project / "agents" / "another.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        ConfigValidator(project).validate_agents_only()
    assert "Duplicate agent_id" in str(exc_info.value)
