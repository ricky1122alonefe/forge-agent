"""Run a single Agent in isolation — Agent-first, no Pipeline (AGENT_PLAN A6)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from forge_agent.core.context import AgentContext
from forge_agent.core.factory import AgentFactory
from forge_agent.platform import LocalTenant
from forge_agent.project.launcher import (
    _ensure_builtin_agents,
    resolve_local_tenant,
)
from forge_agent.project.llm_ready import ensure_llm_ready
from forge_agent.project.state_store import RunRecord, StateStore, generate_run_id
from forge_agent.registry.registry import get_registry
from forge_agent.web.data import get_agent, infer_run_mock_mode


def default_run_payload(agent: dict[str, Any]) -> dict[str, Any]:
    """Pick a sensible default payload from mock_cases or variable names."""
    for case in agent.get("mock_cases") or []:
        if isinstance(case, dict):
            inp = case.get("input")
            if isinstance(inp, dict) and inp:
                return dict(inp)

    config = agent.get("config", {}) if isinstance(agent.get("config"), dict) else {}
    variables = config.get("variables", {}) if isinstance(config.get("variables"), dict) else {}
    payload: dict[str, Any] = {}
    for runtime_key in ("keyword", "query", "topic", "current_value", "threshold", "metric_name"):
        if runtime_key in variables.values() or runtime_key in variables:
            if runtime_key == "current_value":
                payload[runtime_key] = 42
            elif runtime_key == "threshold":
                payload[runtime_key] = float(config.get("threshold", 100))
            else:
                payload[runtime_key] = "demo"
    if "reports" in str(config.get("prompt", "")):
        payload.setdefault(
            "reports",
            [{"agent_id": "upstream", "verdict": "lean_neutral", "confidence": 0.6}],
        )
    return payload


async def run_single_agent(
    project_root: Path,
    tenant_id: str,
    agent_id: str,
    payload: dict[str, Any] | None = None,
    *,
    tenant: LocalTenant | None = None,
    save_record: bool = True,
) -> dict[str, Any]:
    """Load one agent YAML, execute with payload, return structured report."""
    agent_path = project_root / "agents" / f"{agent_id}.yaml"
    if not agent_path.is_file():
        raise FileNotFoundError(f"Agent {agent_id!r} not found")

    agent_entry = get_agent(project_root, agent_id)
    if agent_entry is None:
        raise ValueError(f"Agent {agent_id!r} not found in YAML")

    run_payload = dict(payload or default_run_payload(agent_entry))
    local_tenant = tenant or resolve_local_tenant(tenant_id, project_root)
    config = agent_entry.get("config", {}) if isinstance(agent_entry.get("config"), dict) else {}
    mock_mode = bool(config.get("mock_mode", True))
    if not mock_mode:
        ensure_llm_ready(local_tenant, project_root)

    _ensure_builtin_agents()
    registry = get_registry()
    registry.unregister(agent_id)

    data = yaml.safe_load(agent_path.read_text(encoding="utf-8")) or {}
    agents = data.get("agents", []) if isinstance(data, dict) else data
    factory = AgentFactory()
    for entry in agents:
        if isinstance(entry, dict) and entry.get("agent_id") == agent_id:
            entry = dict(entry)
            entry["override"] = True
            factory.from_dict(entry)
            break
    else:
        raise ValueError(f"Agent {agent_id!r} missing from {agent_path}")

    instance = await registry.get(agent_id, config=config)
    ctx = AgentContext(
        scope_id=f"agent:{agent_id}",
        scope_name=agent_entry.get("name", agent_id),
        payload=run_payload,
    )
    report = await instance.run(ctx)
    report_dict = report.model_dump() if hasattr(report, "model_dump") else dict(report.__dict__)

    result = {
        "success": True,
        "agent_id": agent_id,
        "payload": run_payload,
        "report": report_dict,
        "mock_mode": mock_mode,
        "verdict": str(report.verdict),
    }

    if not mock_mode:
        from forge_agent.agent_spec.maturity import compute_maturity
        from forge_agent.agent_spec.writer import mark_real_run_verified

        mark_real_run_verified(project_root, agent_id)
        updated = get_agent(project_root, agent_id) or agent_entry
        result["maturity"] = compute_maturity(updated)

    if save_record:
        run_id = generate_run_id(f"agent_{agent_id}")
        record = RunRecord(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            pipeline_id=f"agent:{agent_id}",
            pipeline_name=agent_entry.get("name", agent_id),
            tenant_id=tenant_id,
            project_id=project_root.name,
            payload=run_payload,
            agent_reports=[report_dict],
            chief_summary=None,
            metadata={
                "kind": "agent_run",
                "agent_id": agent_id,
                "mock_mode": infer_run_mock_mode([report_dict]),
            },
        )
        StateStore(project_root).save(record)
        result["run_id"] = run_id

    registry.unregister(agent_id)
    return result
