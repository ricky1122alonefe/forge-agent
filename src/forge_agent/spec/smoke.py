"""Mock smoke tests for generated AgentSpec assets."""

from __future__ import annotations

from typing import Any

from forge_agent.core.context import AgentContext
from forge_agent.core.factory import AgentFactory
from forge_agent.spec.models import AgentSpec


async def smoke_run_spec(spec: AgentSpec, case_index: int = 0) -> dict[str, Any]:
    """Load spec into a transient agent and run one mock case."""
    if not spec.mock_cases:
        return {"success": False, "error": "no mock_cases defined"}

    case = spec.mock_cases[case_index]
    factory = AgentFactory()
    agent_dict = {
        "agent_id": spec.agent_id,
        "name": spec.name,
        "domain": spec.domain,
        "template": spec.template,
        "config": dict(spec.config),
        "override": True,
    }
    try:
        cls = factory.from_dict(agent_dict)
        agent = cls(config=spec.config)
        await agent.initialize()

        ctx = AgentContext(
            scope_id="smoke",
            scope_name="AgentSpec smoke",
            payload=dict(case.input),
        )
        report = await agent.run(ctx)
        decision = report.raw.get("decision", {})
        if not isinstance(decision, dict):
            decision = {}
        missing = [k for k in case.expect_keys if k not in decision]
        return {
            "success": not missing and report.agent_id == spec.agent_id,
            "case": case.name,
            "missing_keys": missing,
            "decision_keys": list(decision.keys()),
            "verdict": str(report.verdict),
            "agent_id": report.agent_id,
            "agent_report": report,
        }
    finally:
        from forge_agent.registry.registry import get_registry

        get_registry().unregister(spec.agent_id)


def smoke_run_spec_sync(spec: AgentSpec, case_index: int = 0) -> dict[str, Any]:
    from forge_agent.utils.async_utils import run_sync

    return run_sync(smoke_run_spec(spec, case_index=case_index))


async def smoke_all_cases(spec: AgentSpec) -> list[dict[str, Any]]:
    results = []
    for idx in range(len(spec.mock_cases)):
        results.append(await smoke_run_spec(spec, case_index=idx))
    return results
