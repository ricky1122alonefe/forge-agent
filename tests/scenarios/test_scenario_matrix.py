"""Parametric tests for the 20-scenario acceptance matrix (A2.5)."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.from_type import generate_from_agent_type
from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.scenarios import SCENARIO_MATRIX
from forge_agent.agent_spec.smoke import smoke_run_spec
from forge_agent.agent_spec.writer import validate_spec
from forge_agent.builtin import AgentTypeRegistry


@pytest.mark.parametrize("case", SCENARIO_MATRIX, ids=lambda c: c.scenario_id)
@pytest.mark.asyncio
async def test_scenario_matrix_smoke(case) -> None:
    spec = generate_spec_rule_based(
        case.requirement,
        agent_id=f"matrix_{case.scenario_id.lower()}",
        keyword=case.keyword,
        focus=case.focus,
    )
    assert spec.primitive == case.expected_primitive, (
        f"{case.scenario_id}: expected {case.expected_primitive}, got {spec.primitive}"
    )
    if case.expected_profile is not None:
        assert spec.schema_profile == case.expected_profile
    assert not validate_spec(spec), validate_spec(spec)
    smoke = await smoke_run_spec(spec)
    assert smoke["success"] is True, smoke


def test_scenario_matrix_count() -> None:
    assert len(SCENARIO_MATRIX) == 20


@pytest.mark.asyncio
async def test_generate_from_agent_type_monitor() -> None:
    registry = AgentTypeRegistry()
    type_def = registry.get("monitor")
    spec = generate_from_agent_type(
        type_def,
        "tenant_monitor",
        {"metric_name": "inventory", "threshold": 50},
        requirement="监控库存",
    )
    assert spec.primitive.value == "monitor"
    smoke = await smoke_run_spec(spec)
    assert smoke["success"] is True


@pytest.mark.asyncio
async def test_generate_from_agent_type_generator() -> None:
    registry = AgentTypeRegistry()
    type_def = registry.get("generator")
    spec = generate_from_agent_type(
        type_def,
        "tenant_writer",
        {"topic": "季度报告", "format": "markdown"},
    )
    assert spec.primitive.value == "generator"
    smoke = await smoke_run_spec(spec)
    assert smoke["success"] is True
