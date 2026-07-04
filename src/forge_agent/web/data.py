"""Data helpers for the web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Payload keys the user fills at run time. platform/tool are fixed when creating an Agent.
RUNTIME_PAYLOAD_KEYS = frozenset({"keyword"})


def _load_agent_entries(project_root: Path) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    agents_dir = project_root / "agents"
    if not agents_dir.exists():
        return agents

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        for agent in data.get("agents", []):
            if isinstance(agent, dict):
                agents.append(agent)
    return agents


def list_agents(project_root: Path) -> list[dict[str, Any]]:
    """List all agents defined in the project's agents/ directory."""
    return [
        {
            "agent_id": agent.get("agent_id"),
            "name": agent.get("name", ""),
            "domain": agent.get("domain", "generic"),
        }
        for agent in _load_agent_entries(project_root)
    ]


def get_agent(project_root: Path, agent_id: str) -> dict[str, Any] | None:
    """Return a single agent definition dict."""
    for agent in _load_agent_entries(project_root):
        if agent.get("agent_id") == agent_id:
            return agent
    return None


def get_agent_config(project_root: Path, agent_id: str) -> dict[str, Any]:
    """Return editable config fields for an agent."""
    agent = get_agent(project_root, agent_id) or {}
    config = agent.get("config", {}) if isinstance(agent.get("config"), dict) else {}
    tools = config.get("tools", [])
    if not isinstance(tools, list):
        tools = []
    variables = config.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}
    return {
        "agent_id": agent_id,
        "name": agent.get("name", agent_id),
        "template": agent.get("template", "prompt_agent"),
        "mock_mode": bool(config.get("mock_mode", True)),
        "prompt": config.get("prompt", ""),
        "tools": tools,
        "variables": variables,
    }


def list_pipelines(project_root: Path) -> list[dict[str, Any]]:
    """List all pipelines defined in the project's pipelines/ directory."""
    pipelines: list[dict[str, Any]] = []
    pipelines_dir = project_root / "pipelines"
    if not pipelines_dir.exists():
        return pipelines

    for yaml_file in sorted(pipelines_dir.glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        team = data.get("team", {})
        pipelines.append(
            {
                "pipeline_id": data.get("pipeline_id", yaml_file.stem),
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "agent_ids": team.get("agent_ids", []),
                "chief_id": team.get("chief_id"),
                "mode": team.get("mode", "parallel"),
            }
        )
    return pipelines


def get_pipeline(project_root: Path, pipeline_id: str) -> dict[str, Any] | None:
    for pipeline in list_pipelines(project_root):
        if pipeline.get("pipeline_id") == pipeline_id:
            return pipeline
    return None


def collect_payload_fields(project_root: Path, pipeline_id: str) -> list[dict[str, Any]]:
    """Collect run-time payload fields for a pipeline (typically just keyword)."""
    pipeline = get_pipeline(project_root, pipeline_id)
    if not pipeline:
        return []

    seen: set[str] = set()
    fields: list[dict[str, Any]] = []
    for agent_id in pipeline.get("agent_ids", []):
        config = get_agent_config(project_root, agent_id)
        for var_name, payload_key in config.get("variables", {}).items():
            key = str(payload_key or var_name)
            if key not in RUNTIME_PAYLOAD_KEYS or key in seen:
                continue
            seen.add(key)
            fields.append(
                {
                    "name": key,
                    "label": "关键词",
                    "required": True,
                    "default": "labubu",
                }
            )

    if not fields:
        fields.append(
            {
                "name": "keyword",
                "label": "关键词",
                "required": True,
                "default": "labubu",
            }
        )
    return fields


def extract_chief_report(chief_summary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize chief summary for structured UI rendering."""
    if not chief_summary:
        return None
    report = chief_summary.get("chief_report")
    if isinstance(report, dict):
        return report
    return chief_summary


def infer_run_mock_mode(agent_reports: list[dict[str, Any]]) -> bool:
    """Return True when all agent reports were produced in mock mode."""
    if not agent_reports:
        return True
    for report in agent_reports:
        raw = report.get("raw") if isinstance(report.get("raw"), dict) else {}
        decision = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}
        config = decision.get("config") if isinstance(decision.get("config"), dict) else {}
        if config.get("mock_mode") is False:
            return False
    return True


def summarize_project_mock_mode(project_root: Path) -> dict[str, Any]:
    """Summarize mock vs real agents in a project."""
    agents = list_agents(project_root)
    if not agents:
        return {"total": 0, "mock_count": 0, "all_mock": True, "any_mock": False}

    mock_count = sum(
        1 for agent in agents if get_agent_config(project_root, agent["agent_id"])["mock_mode"]
    )
    total = len(agents)
    return {
        "total": total,
        "mock_count": mock_count,
        "all_mock": mock_count == total,
        "any_mock": mock_count > 0,
    }


def get_pipeline_run_plan(project_root: Path, pipeline_id: str) -> list[dict[str, Any]]:
    """Build UI run steps for a pipeline (agents + optional chief)."""
    pipeline = get_pipeline(project_root, pipeline_id)
    if not pipeline:
        return []

    steps: list[dict[str, Any]] = []
    for agent_id in pipeline.get("agent_ids", []):
        config = get_agent_config(project_root, agent_id)
        steps.append(
            {
                "step_id": agent_id,
                "label": config.get("name") or agent_id,
                "kind": "agent",
                "mock_mode": config.get("mock_mode", True),
            }
        )

    chief_id = pipeline.get("chief_id")
    if chief_id:
        chief_config = get_agent_config(project_root, chief_id)
        chief_mock = chief_config.get("mock_mode", True) if chief_config.get("agent_id") else True
        steps.append(
            {
                "step_id": chief_id,
                "label": "Chief 汇总决策",
                "kind": "chief",
                "mock_mode": chief_mock,
            }
        )
    return steps


def summarize_pipeline_mock_mode(project_root: Path, pipeline_id: str) -> dict[str, Any]:
    """Summarize whether a pipeline run will use mock data."""
    steps = get_pipeline_run_plan(project_root, pipeline_id)
    if not steps:
        return {"all_mock": True, "any_mock": False, "step_count": 0}

    mock_count = sum(1 for step in steps if step.get("mock_mode", True))
    return {
        "all_mock": mock_count == len(steps),
        "any_mock": mock_count > 0,
        "step_count": len(steps),
        "mock_count": mock_count,
    }


def load_run_trace(project_root: Path, trace_id: str) -> dict[str, Any] | None:
    """Load a persisted trace JSON for a run, if available."""
    if not trace_id:
        return None
    from forge_agent.observability.persistence import TraceStore

    trace = TraceStore(project_root / "logs").get(trace_id)
    if trace is None:
        return None
    return trace.to_dict()


def format_trace_timeline(trace_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build a simplified span timeline for the web run detail page."""
    if not trace_data:
        return []

    steps: list[dict[str, Any]] = []
    for span in trace_data.get("spans", []):
        if not isinstance(span, dict):
            continue
        span_type = span.get("span_type", "")
        name = span.get("name", "")
        if span_type not in {"agent", "pipeline"} and not name.endswith(".run"):
            continue
        label = name
        if span_type == "agent" or name.endswith(".run"):
            agent_id = span.get("attributes", {}).get("agent_id")
            if agent_id:
                label = agent_id
        steps.append(
            {
                "name": label,
                "span_type": span_type,
                "duration_ms": span.get("duration_ms", 0.0),
                "status": span.get("status", "ok"),
            }
        )
    return steps
