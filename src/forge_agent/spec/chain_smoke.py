"""Full-chain mock smoke for composed pipelines (AGENT_PLAN A10.2)."""

from __future__ import annotations

from typing import Any

from forge_agent.core.factory import AgentFactory
from forge_agent.core.mission import Mission
from forge_agent.core.runner import TeamRunner
from forge_agent.core.team import Team
from forge_agent.registry.registry import get_registry
from forge_agent.spec.ci import CIGateError
from forge_agent.spec.compose import ComposePlan
from forge_agent.spec.models import AgentPrimitive
from forge_agent.spec.writer import spec_to_agent_dict
from forge_agent.storage import ForgeStore


def default_chain_payload(plan: ComposePlan) -> dict[str, Any]:
    """Build a mock pipeline payload from compose plan keyword."""
    payload: dict[str, Any] = {"keyword": plan.keyword or "demo"}
    if any(s.primitive == AgentPrimitive.SEARCHER for s in plan.specs):
        payload["query"] = plan.keyword or "demo"
    return payload


async def smoke_compose_chain(
    plan: ComposePlan,
    *,
    payload: dict[str, Any] | None = None,
    store_path: str = ":memory:",
) -> dict[str, Any]:
    """Run agents in team mode (sequential/parallel) without writing YAML."""
    if len(plan.specs) < 2:
        return {"success": True, "skipped": True, "reason": "single agent plan"}

    run_payload = dict(payload or default_chain_payload(plan))
    factory = AgentFactory()
    registered: list[str] = []

    try:
        for spec in plan.specs:
            entry = spec_to_agent_dict(spec)
            entry["override"] = True
            factory.from_dict(entry)
            registered.append(spec.agent_id)

        team = Team(
            team_id=f"{plan.pipeline_id}_team",
            name=plan.pipeline_name,
            domain="generic",
            agent_ids=list(plan.agent_ids),
            mode=plan.mode,
        )
        mission = Mission(
            mission_id=f"chain_smoke_{plan.pipeline_id}",
            name=f"Chain smoke: {plan.pipeline_name}",
            team=team,
            payload=run_payload,
        )
        board = await TeamRunner(store=ForgeStore(db_path=store_path)).run(mission)

        if len(board.agents) != len(plan.agent_ids):
            raise CIGateError(
                f"chain smoke incomplete: expected {len(plan.agent_ids)} reports, "
                f"got {len(board.agents)}",
                [{"agents_expected": len(plan.agent_ids), "agents_got": len(board.agents)}],
            )

        last = board.agents[-1]
        if plan.specs[-1].primitive == AgentPrimitive.SYNTHESIZER:
            if last.agent_id != plan.specs[-1].agent_id:
                raise CIGateError(
                    f"chain smoke: last agent expected {plan.specs[-1].agent_id!r}, "
                    f"got {last.agent_id!r}",
                    [],
                )
            if not last.evidence and not last.raw:
                raise CIGateError("chain smoke: synthesizer produced empty report", [])

        return {
            "success": True,
            "agents_run": len(board.agents),
            "mode": plan.mode,
            "payload": run_payload,
            "last_verdict": str(last.verdict),
            "last_agent_id": last.agent_id,
        }
    finally:
        registry = get_registry()
        for agent_id in registered:
            registry.unregister(agent_id)
