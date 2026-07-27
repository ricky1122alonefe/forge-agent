"""Scenario matrix coverage report for AgentSpec routing (A4.3)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from forge_agent.spec.generator import generate_spec_rule_based
from forge_agent.spec.scenarios import SCENARIO_MATRIX


def compute_scenario_coverage() -> dict[str, Any]:
    """Evaluate rule-based routing against the 20-scenario acceptance matrix."""
    scenarios: list[dict[str, Any]] = []
    primitive_hits: Counter[str] = Counter()
    profile_hits: Counter[str] = Counter()
    routing_pass = 0

    for case in SCENARIO_MATRIX:
        spec = generate_spec_rule_based(
            case.requirement,
            agent_id=f"coverage_{case.scenario_id.lower()}",
            keyword=case.keyword,
            focus=case.focus,
        )
        primitive_ok = spec.primitive == case.expected_primitive
        profile_ok = case.expected_profile is None or spec.schema_profile == case.expected_profile
        routing_ok = primitive_ok and profile_ok
        if routing_ok:
            routing_pass += 1

        primitive_hits[spec.primitive.value] += 1
        profile_hits[spec.schema_profile.value] += 1
        scenarios.append(
            {
                "scenario_id": case.scenario_id,
                "requirement": case.requirement,
                "expected_primitive": case.expected_primitive.value,
                "actual_primitive": spec.primitive.value,
                "expected_profile": case.expected_profile.value if case.expected_profile else None,
                "actual_profile": spec.schema_profile.value,
                "routing_ok": routing_ok,
                "primitive_ok": primitive_ok,
                "profile_ok": profile_ok,
            }
        )

    total = len(SCENARIO_MATRIX)
    return {
        "total": total,
        "routing_pass": routing_pass,
        "routing_rate": round(routing_pass / total, 4) if total else 0.0,
        "target_rate": 0.9,
        "target_met": routing_pass >= 18,
        "by_primitive": dict(sorted(primitive_hits.items())),
        "by_profile": dict(sorted(profile_hits.items())),
        "scenarios": scenarios,
    }
