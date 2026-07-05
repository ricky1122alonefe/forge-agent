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
        "schema_profile": spec.schema_profile.value,
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
    smoke_verified: bool = False,
) -> dict[str, Any]:
    """Validate, write YAML, return result metadata."""
    errors = validate_spec(spec)
    if errors:
        raise ValueError("; ".join(errors))

    agents_dir = project_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{spec.agent_id}.yaml"
    if path.exists() and not overwrite:
        raise ValueError(f"Agent {spec.agent_id!r} already exists")

    agent_dict = spec_to_agent_dict(spec)
    if smoke_verified:
        agent_dict["_meta"]["smoke_verified"] = True
        agent_dict["_meta"]["maturity"] = "verified"

    path.write_text(
        yaml.safe_dump({"agents": [agent_dict]}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "success": True,
        "agent_id": spec.agent_id,
        "path": str(path),
        "primitive": spec.primitive.value,
        "planner": spec.planner,
        "mock_cases": len(spec.mock_cases),
        "smoke_verified": smoke_verified,
    }


def mark_smoke_verified(project_root: Path, agent_id: str) -> None:
    """Persist smoke_verified flag on an existing agent YAML."""
    from forge_agent.web.data import get_agent

    agent = get_agent(project_root, agent_id)
    if agent is None:
        return
    meta = dict(agent.get("_meta") or {})
    meta["smoke_verified"] = True
    meta["maturity"] = "verified"
    agent["_meta"] = meta
    path = project_root / "agents" / f"{agent_id}.yaml"
    path.write_text(
        yaml.safe_dump({"agents": [agent]}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def agent_dict_to_spec(agent: dict[str, Any]) -> AgentSpec:
    """Rebuild AgentSpec from a stored agent YAML entry (for smoke re-runs)."""
    from forge_agent.agent_spec.models import AgentPrimitive, MockCase, SchemaProfile

    meta = agent.get("_meta") or {}
    try:
        primitive = AgentPrimitive(meta.get("primitive", AgentPrimitive.REASONER.value))
    except ValueError:
        primitive = AgentPrimitive.REASONER
    try:
        profile = SchemaProfile(meta.get("schema_profile", SchemaProfile.ANALYSIS.value))
    except ValueError:
        profile = SchemaProfile.ANALYSIS
    cases = [MockCase(**c) if isinstance(c, dict) else c for c in agent.get("mock_cases", [])]
    if not cases:
        cases = [MockCase(name="default", input={}, expect_keys=[])]
    return AgentSpec(
        agent_id=str(agent["agent_id"]),
        name=str(agent.get("name", agent["agent_id"])),
        domain=str(agent.get("domain", "generic")),
        template=str(agent.get("template", "prompt_agent")),
        primitive=primitive,
        schema_profile=profile,
        config=dict(agent.get("config", {})),
        mock_cases=cases,
    )
