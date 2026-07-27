"""Primitive wire contracts for auto-composed pipelines (AGENT_PLAN A9.1)."""

from __future__ import annotations

from dataclasses import dataclass

from forge_agent.spec.models import AgentPrimitive

EMITTER_PRIMITIVES = frozenset(
    {
        AgentPrimitive.FETCHER,
        AgentPrimitive.SEARCHER,
        AgentPrimitive.REASONER,
    }
)


@dataclass(frozen=True)
class WireRule:
    """Plug specification for one agent primitive."""

    consumes_payload: frozenset[str]
    consumes_reports: bool
    emits_report: bool
    pairs_with: frozenset[AgentPrimitive]


PRIMITIVE_WIRE: dict[AgentPrimitive, WireRule] = {
    AgentPrimitive.FETCHER: WireRule(
        consumes_payload=frozenset({"keyword"}),
        consumes_reports=False,
        emits_report=True,
        pairs_with=frozenset({AgentPrimitive.SYNTHESIZER}),
    ),
    AgentPrimitive.SEARCHER: WireRule(
        consumes_payload=frozenset({"query"}),
        consumes_reports=False,
        emits_report=True,
        pairs_with=frozenset({AgentPrimitive.SYNTHESIZER}),
    ),
    AgentPrimitive.REASONER: WireRule(
        consumes_payload=frozenset({"topic"}),
        consumes_reports=False,
        emits_report=True,
        pairs_with=frozenset({AgentPrimitive.SYNTHESIZER}),
    ),
    AgentPrimitive.SYNTHESIZER: WireRule(
        consumes_payload=frozenset(),
        consumes_reports=True,
        emits_report=True,
        pairs_with=frozenset(),
    ),
    AgentPrimitive.MONITOR: WireRule(
        consumes_payload=frozenset({"current_value", "threshold"}),
        consumes_reports=False,
        emits_report=True,
        pairs_with=frozenset(),
    ),
    AgentPrimitive.GENERATOR: WireRule(
        consumes_payload=frozenset({"topic", "format"}),
        consumes_reports=False,
        emits_report=True,
        pairs_with=frozenset(),
    ),
}


def suggest_team_mode(primitives: list[AgentPrimitive]) -> str:
    """Return sequential when upstream reports must flow, else parallel."""
    if AgentPrimitive.SYNTHESIZER in primitives:
        return "sequential"
    return "parallel"


def validate_wiring(primitives: list[AgentPrimitive]) -> list[str]:
    """Validate primitive ordering for auto-wired sequential pipelines."""
    errors: list[str] = []
    if not primitives:
        errors.append("empty agent list")
        return errors

    if AgentPrimitive.SYNTHESIZER in primitives:
        synth_idx = primitives.index(AgentPrimitive.SYNTHESIZER)
        if synth_idx == 0:
            errors.append("synthesizer requires at least one upstream agent")
        else:
            upstream = primitives[:synth_idx]
            if not upstream:
                errors.append("synthesizer requires at least one upstream agent")
            for primitive in upstream:
                if primitive not in EMITTER_PRIMITIVES:
                    errors.append(
                        f"{primitive.value} cannot feed synthesizer; "
                        f"expected one of: {', '.join(sorted(p.value for p in EMITTER_PRIMITIVES))}"
                    )
        if primitives.count(AgentPrimitive.SYNTHESIZER) > 1:
            errors.append("only one synthesizer allowed per composed pipeline")

    return errors
