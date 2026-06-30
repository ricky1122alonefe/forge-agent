"""Build agent YAML definitions from agent type templates and user parameters."""

from __future__ import annotations

import re
from typing import Any

import yaml


def _render_template(template: str, variables: dict[str, Any]) -> str:
    """Replace {var} placeholders in a template, leaving unknown placeholders intact."""

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in variables:
            return str(variables[key])
        return match.group(0)

    return re.sub(r"\{(\w+)\}", replacer, template)


def build_agent(
    type_def: dict[str, Any],
    agent_id: str,
    params: dict[str, Any],
    *,
    mock_mode: bool = True,
) -> dict[str, Any]:
    """Instantiate an agent definition from an agent type and user parameters.

    Args:
        type_def: The agent type definition loaded from AgentTypeRegistry.
        agent_id: Unique agent id for the generated agent.
        params: User-provided parameters for this agent.
        mock_mode: Whether to include mock response for offline/demo use.

    Returns:
        A dictionary representing a single agent YAML entry.
    """
    prompt_template = type_def.get("prompt_template", "")
    prompt = _render_template(prompt_template, params)

    tools = type_def.get("tools", [])
    rendered_tools = [_render_template(tool, params) for tool in tools]

    config: dict[str, Any] = {
        "mock_mode": mock_mode,
        "prompt": prompt,
        "output_schema": type_def.get("output_schema", {}),
        "output_mapping": type_def.get("output_mapping", {}),
    }

    if rendered_tools:
        config["tools"] = rendered_tools

    mock_response = type_def.get("mock_response")
    if mock_response:
        config["mock_response"] = _render_template(mock_response.strip(), params)

    # Collect declared variables so the runner knows how to map payload fields.
    config["variables"] = {p["name"]: p["name"] for p in type_def.get("params", [])}

    return {
        "agent_id": agent_id,
        "name": type_def.get("name", agent_id),
        "domain": type_def.get("domain", "generic"),
        "template": type_def.get("template", "prompt_agent"),
        "config": config,
    }


def build_agent_yaml(
    type_def: dict[str, Any],
    agent_id: str,
    params: dict[str, Any],
    *,
    mock_mode: bool = True,
) -> str:
    """Build and serialize a single agent YAML file."""
    agent = build_agent(type_def, agent_id, params, mock_mode=mock_mode)
    return yaml.safe_dump({"agents": [agent]}, sort_keys=False, allow_unicode=True)


def build_pipeline(
    pipeline_id: str,
    name: str,
    agent_ids: list[str],
    *,
    chief_id: str | None = None,
    mode: str = "parallel",
    description: str = "",
) -> dict[str, Any]:
    """Build a pipeline definition from selected agents."""
    team: dict[str, Any] = {
        "team_id": f"{pipeline_id}_team",
        "name": f"{name} Team",
        "domain": "generic",
        "agent_ids": agent_ids,
        "mode": mode,
    }
    if chief_id:
        team["chief_id"] = chief_id

    return {
        "pipeline_id": pipeline_id,
        "name": name,
        "description": description,
        "team": team,
    }


def build_pipeline_yaml(
    pipeline_id: str,
    name: str,
    agent_ids: list[str],
    *,
    chief_id: str | None = None,
    mode: str = "parallel",
    description: str = "",
) -> str:
    """Build and serialize a pipeline YAML file."""
    pipeline = build_pipeline(
        pipeline_id, name, agent_ids, chief_id=chief_id, mode=mode, description=description
    )
    return yaml.safe_dump(pipeline, sort_keys=False, allow_unicode=True)
