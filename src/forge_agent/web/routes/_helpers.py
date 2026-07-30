"""Shared helpers for API route sub-modules (S4.1).

Extracted from the original monolithic api.py to enable per-domain
route files. Each sub-route imports Ctx and path helpers from here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import Depends, HTTPException

from forge_agent.project.agent_builder import build_pipeline_yaml
from forge_agent.project.agent_runner import default_run_payload, run_single_agent
from forge_agent.project.launcher import _run_pipeline
from forge_agent.project.llm_ready import ensure_llm_ready
from forge_agent.spec import AgentSpec, apply_spec, generate_from_agent_type, mark_smoke_verified
from forge_agent.web.agent_types import registry_for
from forge_agent.web.context import ProjectContext, get_project_context, project_url
from forge_agent.web.data import collect_payload_fields, get_agent_config
from forge_agent.web.data import get_agent as load_agent_dict
from forge_agent.web.llm_runtime import resolve_llm_chat
from forge_agent.web.presets import get_pipeline_preset, get_preset

Ctx = Annotated[ProjectContext, Depends(get_project_context)]


def _agent_path(project_root: Path, agent_id: str) -> Path:
    return project_root / "agents" / f"{agent_id}.yaml"


def _pipeline_path(project_root: Path, pipeline_id: str) -> Path:
    return project_root / "pipelines" / f"{pipeline_id}.yaml"


def _shared_market_dir(ctx: Ctx) -> Path:
    return ctx.tenant.get_shared_path() / "market"


async def _apply_agent_spec(
    ctx: Ctx,
    spec: AgentSpec,
    *,
    overwrite: bool = False,
    run_smoke: bool = True,
    ci_gate: bool | None = None,
    auto_repair: bool = True,
    judge_gate: bool = True,
) -> dict[str, Any]:
    from forge_agent.spec.ci import CIGateError

    gate = run_smoke if ci_gate is None else ci_gate
    try:
        result = apply_spec(
            ctx.project_root,
            spec,
            overwrite=overwrite,
            ci_gate=gate,
            auto_repair=auto_repair and gate,
            judge_gate=judge_gate and gate,
        )
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if gate and spec.mock_cases and result.get("success"):
        mark_smoke_verified(ctx.project_root, spec.agent_id)
        result["smoke_verified"] = True
        if result.get("smoke_results"):
            first = result["smoke_results"][0]
            result["smoke"] = first
            if first.get("judge"):
                result["judge"] = first["judge"]
    return result


async def _create_agent_from_type(
    ctx: Ctx,
    agent_type: str,
    agent_id: str,
    params: dict[str, Any],
    *,
    requirement: str = "",
    overwrite: bool = False,
    run_smoke: bool = True,
) -> dict[str, Any]:
    try:
        type_def = registry_for(ctx).get(agent_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = _agent_path(ctx.project_root, agent_id)
    if target.exists() and not overwrite:
        raise HTTPException(status_code=409, detail=f"Agent {agent_id!r} already exists")

    spec = generate_from_agent_type(type_def, agent_id, params, requirement=requirement)
    try:
        ensure_llm_ready(ctx.tenant, ctx.project_root)
        spec.config["mock_mode"] = False
    except Exception:
        pass
    try:
        result = await _apply_agent_spec(ctx, spec, overwrite=overwrite, run_smoke=run_smoke)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        **result,
        "agent_id": spec.agent_id,
        "path": str(target),
        "primitive": spec.primitive.value,
        "planner": spec.planner,
        "agent_url": project_url(ctx.tenant_id, ctx.project_id, f"/agents/{spec.agent_id}"),
    }


async def _ensure_agent_from_preset(preset_id: str, ctx: Ctx) -> tuple[str, bool]:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Agent preset {preset_id!r} not found")

    agent_id = preset["default_agent_id"]
    if _agent_path(ctx.project_root, agent_id).exists():
        return agent_id, False

    from forge_agent.web.routes._helpers import _create_agent_from_type

    await _create_agent_from_type(
        ctx,
        preset["agent_type"],
        agent_id,
        preset.get("params", {}),
    )
    return agent_id, True


def _merge_agent_config_yaml(agent_id: str, yaml_text: str, updates: Any) -> str:
    data = yaml.safe_load(yaml_text) or {}
    agents = data.get("agents", []) if isinstance(data, dict) else data
    if not isinstance(agents, list):
        raise ValueError("Agent YAML must contain an 'agents' list")

    target_agent: dict[str, Any] | None = None
    for agent in agents:
        if isinstance(agent, dict) and agent.get("agent_id") == agent_id:
            target_agent = agent
            break
    if target_agent is None:
        raise ValueError(f"Agent {agent_id!r} not found in YAML")

    config = target_agent.setdefault("config", {})
    if not isinstance(config, dict):
        raise ValueError("Agent config must be a mapping")

    if updates.mock_mode is not None:
        config["mock_mode"] = updates.mock_mode
    if updates.prompt is not None:
        config["prompt"] = updates.prompt
    if updates.tools is not None:
        config["tools"] = updates.tools

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


__all__ = [
    "Ctx",
    "_agent_path",
    "_apply_agent_spec",
    "_create_agent_from_type",
    "_ensure_agent_from_preset",
    "_merge_agent_config_yaml",
    "_pipeline_path",
    "_run_pipeline",
    "_shared_market_dir",
    "build_pipeline_yaml",
    "collect_payload_fields",
    "default_run_payload",
    "ensure_llm_ready",
    "get_agent_config",
    "get_pipeline_preset",
    "get_preset",
    "load_agent_dict",
    "project_url",
    "registry_for",
    "resolve_llm_chat",
    "run_single_agent",
]
