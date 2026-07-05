"""Write AgentSpec to project agents/ and validate structure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge_agent.agent_spec.models import AgentSpec


def spec_to_agent_dict(spec: AgentSpec) -> dict[str, Any]:
    """Convert AgentSpec to a single agent YAML entry."""
    agent: dict[str, Any] = {
        "agent_id": spec.agent_id,
        "name": spec.name,
        "domain": spec.domain,
        "template": spec.template,
        "tags": list(spec.tags),
        "config": dict(spec.config),
    }
    if spec.mock_cases:
        agent["mock_cases"] = [c.to_dict() for c in spec.mock_cases]
    agent["_meta"] = {
        "primitive": spec.primitive.value,
        "requirement": spec.requirement,
        "planner": spec.planner,
    }
    return agent


def validate_spec(spec: AgentSpec) -> list[str]:
    """Return validation errors (empty list = ok)."""
    errors: list[str] = []
    if not spec.agent_id or not re_valid_id(spec.agent_id):
        errors.append(f"invalid agent_id: {spec.agent_id!r}")
    if not spec.name:
        errors.append("name is required")
    if not spec.template:
        errors.append("template is required")
    config = spec.config
    if (
        not config.get("prompt")
        and spec.template != "scraper_agent"
        and spec.template == "search_agent"
        and not config.get("query_template")
    ):
        errors.append("search_agent requires query_template or prompt")
    if not config.get("output_schema"):
        errors.append("output_schema is required")
    if not config.get("output_mapping"):
        errors.append("output_mapping is required")
    if spec.template in {"scraper_agent", "tool_agent"} and not config.get("tools"):
        errors.append("fetcher agents require tools")
    return errors


def re_valid_id(agent_id: str) -> bool:
    import re

    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_.-]*$", agent_id))


def write_agent_yaml(
    project_root: Path,
    spec: AgentSpec,
    *,
    overwrite: bool = False,
) -> Path:
    """Write agents/{agent_id}.yaml from an AgentSpec."""
    errors = validate_spec(spec)
    if errors:
        raise ValueError("; ".join(errors))

    agents_dir = project_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{spec.agent_id}.yaml"
    if path.exists() and not overwrite:
        raise ValueError(f"Agent {spec.agent_id!r} already exists")

    doc = {"agents": [spec_to_agent_dict(spec)]}
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def apply_spec(
    project_root: Path,
    spec: AgentSpec,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate, write YAML, return result metadata."""
    path = write_agent_yaml(project_root, spec, overwrite=overwrite)
    return {
        "success": True,
        "agent_id": spec.agent_id,
        "path": str(path),
        "primitive": spec.primitive.value,
        "planner": spec.planner,
        "mock_cases": len(spec.mock_cases),
    }
