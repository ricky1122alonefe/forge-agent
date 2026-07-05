"""AgentSpec — generate, validate, and write reusable Agent assets."""

from forge_agent.agent_spec.generator import (
    detect_primitive,
    extract_keyword,
    generate_spec,
    generate_spec_rule_based,
)
from forge_agent.agent_spec.models import AgentPrimitive, AgentSpec, MockCase
from forge_agent.agent_spec.smoke import smoke_all_cases, smoke_run_spec, smoke_run_spec_sync
from forge_agent.agent_spec.writer import (
    apply_spec,
    spec_to_agent_dict,
    validate_spec,
    write_agent_yaml,
)

__all__ = [
    "AgentPrimitive",
    "AgentSpec",
    "MockCase",
    "apply_spec",
    "detect_primitive",
    "extract_keyword",
    "generate_spec",
    "generate_spec_rule_based",
    "smoke_all_cases",
    "smoke_run_spec",
    "smoke_run_spec_sync",
    "spec_to_agent_dict",
    "validate_spec",
    "write_agent_yaml",
]
