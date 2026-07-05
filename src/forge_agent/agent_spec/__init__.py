"""AgentSpec — generate, validate, and write reusable Agent assets."""

from forge_agent.agent_spec.compose import ComposePlan, apply_compose_plan, compose_from_requirement
from forge_agent.agent_spec.from_type import generate_from_agent_type
from forge_agent.agent_spec.generator import (
    detect_primitive,
    detect_schema_profile,
    extract_keyword,
    generate_spec,
    generate_spec_rule_based,
)
from forge_agent.agent_spec.models import AgentPrimitive, AgentSpec, MockCase, SchemaProfile
from forge_agent.agent_spec.scenarios import SCENARIO_MATRIX, ScenarioCase
from forge_agent.agent_spec.smoke import smoke_all_cases, smoke_run_spec, smoke_run_spec_sync
from forge_agent.agent_spec.tool_match import list_tool_catalog, match_platforms
from forge_agent.agent_spec.versioning import (
    AGENT_ASSET_SPEC_VERSION,
    validate_agent_asset,
)
from forge_agent.agent_spec.writer import (
    agent_dict_to_spec,
    apply_spec,
    mark_real_run_verified,
    mark_smoke_verified,
    spec_to_agent_dict,
    validate_spec,
    write_agent_yaml,
)

__all__ = [
    "AGENT_ASSET_SPEC_VERSION",
    "SCENARIO_MATRIX",
    "AgentPrimitive",
    "AgentSpec",
    "ComposePlan",
    "MockCase",
    "ScenarioCase",
    "SchemaProfile",
    "agent_dict_to_spec",
    "apply_compose_plan",
    "apply_spec",
    "compose_from_requirement",
    "detect_primitive",
    "detect_schema_profile",
    "extract_keyword",
    "generate_from_agent_type",
    "generate_spec",
    "generate_spec_rule_based",
    "list_tool_catalog",
    "mark_real_run_verified",
    "mark_smoke_verified",
    "match_platforms",
    "smoke_all_cases",
    "smoke_run_spec",
    "smoke_run_spec_sync",
    "spec_to_agent_dict",
    "validate_agent_asset",
    "validate_spec",
    "write_agent_yaml",
]
