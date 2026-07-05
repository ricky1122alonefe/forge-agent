"""Mock smoke tests for generated AgentSpec assets."""

from __future__ import annotations

import asyncio
from typing import Any

from forge_agent.agent_spec.models import AgentSpec
from forge_agent.core.context import AgentContext
from forge_agent.core.factory import AgentFactory


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
    missing = [k for k in case.expect_keys if k not in decision]
    return {
        "success": not missing and report.agent_id == spec.agent_id,
        "case": case.name,
        "missing_keys": missing,
        "verdict": str(report.verdict),
        "agent_id": report.agent_id,
    }


def smoke_run_spec_sync(spec: AgentSpec, case_index: int = 0) -> dict[str, Any]:
    return asyncio.run(smoke_run_spec(spec, case_index=case_index))


async def smoke_all_cases(spec: AgentSpec) -> list[dict[str, Any]]:
    results = []
    for idx in range(len(spec.mock_cases)):
        results.append(await smoke_run_spec(spec, case_index=idx))
    return results
