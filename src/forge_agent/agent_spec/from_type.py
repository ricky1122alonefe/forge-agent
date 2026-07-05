"""Generate AgentSpec from registered agent types (A2.3)."""

from __future__ import annotations

from typing import Any

from forge_agent.agent_spec.capabilities import merge_type_capabilities
from forge_agent.agent_spec.generator import _default_mock_cases, _primitive_from_type_id
from forge_agent.agent_spec.models import AgentSpec, SchemaProfile
from forge_agent.project.agent_builder import build_agent


def generate_from_agent_type(
    type_def: dict[str, Any],
    agent_id: str,
    params: dict[str, Any],
    *,
    requirement: str = "",
    mock_mode: bool = True,
) -> AgentSpec:
    """Build an AgentSpec from an AgentTypeRegistry entry."""
    agent = build_agent(type_def, agent_id, params, mock_mode=mock_mode)
    type_id = str(type_def.get("type_id", "custom"))
    primitive = _primitive_from_type_id(type_id)
    profile = _schema_profile_from_params(type_id, params)
    mock_cases = _default_mock_cases(primitive, params, profile)

    spec = AgentSpec(
        agent_id=agent_id,
        name=str(agent.get("name", agent_id)),
        domain=str(agent.get("domain", "generic")),
        template=str(agent.get("template", "prompt_agent")),
        primitive=primitive,
        schema_profile=profile,
        description=str(type_def.get("description", requirement)),
        requirement=requirement or str(type_def.get("description", "")),
        planner="agent_type",
        tags=["generated", f"type:{type_id}"],
        config=dict(agent.get("config", {})),
        mock_cases=mock_cases,
    )
    return merge_type_capabilities(spec, type_def.get("capabilities"))


def _schema_profile_from_type(type_id: str) -> SchemaProfile:
    mapping = {
        "scraper": SchemaProfile.ANALYSIS,
        "search": SchemaProfile.ANALYSIS,
        "synthesizer": SchemaProfile.ANALYSIS,
        "analyzer": SchemaProfile.ANALYSIS,
        "reasoner": SchemaProfile.ANALYSIS,
        "monitor": SchemaProfile.MONITOR,
        "generator": SchemaProfile.GENERATE,
    }
    profile_name = str(type_id).lower()
    if profile_name == "reasoner":
        return SchemaProfile.ANALYSIS
    return mapping.get(type_id, SchemaProfile.ANALYSIS)


def _schema_profile_from_params(type_id: str, params: dict[str, Any]) -> SchemaProfile:
    if type_id == "reasoner":
        raw = str(params.get("schema_profile", "analysis")).lower()
        try:
            return SchemaProfile(raw)
        except ValueError:
            return SchemaProfile.ANALYSIS
    return _schema_profile_from_type(type_id)
