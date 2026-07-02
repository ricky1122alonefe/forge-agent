"""Data helpers for the web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def list_agents(project_root: Path) -> list[dict[str, Any]]:
    """List all agents defined in the project's agents/ directory."""
    agents: list[dict[str, Any]] = []
    agents_dir = project_root / "agents"
    if not agents_dir.exists():
        return agents

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        for agent in data.get("agents", []):
            agents.append(
                {
                    "agent_id": agent.get("agent_id"),
                    "name": agent.get("name", ""),
                    "domain": agent.get("domain", "generic"),
                }
            )
    return agents


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
            }
        )
    return pipelines
