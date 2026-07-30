"""Agent CRUD, presets, config, smoke, run routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from forge_agent.spec import (
    agent_dict_to_spec,
    mark_smoke_verified,
    smoke_run_spec,
)
from forge_agent.spec.versioning import validate_agent_asset
from forge_agent.web.presets import AGENT_PRESETS, get_preset
from forge_agent.web.routes._helpers import (
    Ctx,
    _agent_path,
    _create_agent_from_type,
    _merge_agent_config_yaml,
    default_run_payload,
    get_agent_config,
    load_agent_dict,
    run_single_agent,
)

router = APIRouter()


class CreateAgentPayload(BaseModel):
    agent_type: str
    agent_id: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents")
async def create_agent(payload: CreateAgentPayload, ctx: Ctx) -> dict[str, Any]:
    return await _create_agent_from_type(ctx, payload.agent_type, payload.agent_id, payload.params)


@router.get("/agent-presets")
async def list_agent_presets() -> dict[str, Any]:
    return {"presets": AGENT_PRESETS}


class CreateAgentFromPresetPayload(BaseModel):
    preset_id: str
    agent_id: str | None = None


@router.post("/agents/from-preset")
async def create_agent_from_preset(
    payload: CreateAgentFromPresetPayload, ctx: Ctx
) -> dict[str, Any]:
    preset = get_preset(payload.preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Preset {payload.preset_id!r} not found")
    agent_id = payload.agent_id or preset["default_agent_id"]
    return await create_agent(
        CreateAgentPayload(
            agent_type=preset["agent_type"],
            agent_id=agent_id,
            params=preset.get("params", {}),
        ),
        ctx,
    )


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return {"agent_id": agent_id, "yaml": target.read_text(encoding="utf-8")}


@router.get("/agents/{agent_id}/validate")
async def validate_agent_asset_api(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    from forge_agent.spec.versioning import AGENT_ASSET_SPEC_VERSION

    agent = load_agent_dict(ctx.project_root, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    errors = validate_agent_asset(agent)
    meta = agent.get("_meta") if isinstance(agent.get("_meta"), dict) else {}
    return {
        "valid": not errors,
        "errors": errors,
        "spec_version": meta.get("spec_version"),
        "revision": meta.get("revision"),
        "expected_spec_version": AGENT_ASSET_SPEC_VERSION,
    }


@router.post("/agents/{agent_id}/migrate")
async def migrate_agent_asset(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    from forge_agent.spec.versioning import migrate_agent_dict, validate_agent_asset

    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    agents = raw.get("agents", []) if isinstance(raw, dict) else raw
    migrated = False
    for entry in agents:
        if isinstance(entry, dict) and entry.get("agent_id") == agent_id:
            entry.update(migrate_agent_dict(entry))
            migrated = True
            break
    if not migrated:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found in YAML")
    target.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    agent = load_agent_dict(ctx.project_root, agent_id) or {}
    meta = agent.get("_meta") if isinstance(agent.get("_meta"), dict) else {}
    return {
        "success": True,
        "agent_id": agent_id,
        "spec_version": meta.get("spec_version"),
        "revision": meta.get("revision"),
        "primitive": meta.get("primitive"),
        "validation_errors": validate_agent_asset(agent),
    }


@router.get("/agents/{agent_id}/config")
async def get_agent_config_api(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return get_agent_config(ctx.project_root, agent_id)


class UpdateAgentConfigPayload(BaseModel):
    mock_mode: bool | None = None
    prompt: str | None = None
    tools: list[str] | None = None
    run_ci: bool = True


@router.put("/agents/{agent_id}/config")
async def update_agent_config(
    agent_id: str, payload: UpdateAgentConfigPayload, ctx: Ctx
) -> dict[str, Any]:
    from forge_agent.spec.ci import CIGateError, persist_agent_document_with_ci

    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    try:
        merged_text = _merge_agent_config_yaml(
            agent_id, target.read_text(encoding="utf-8"), payload
        )
        document = yaml.safe_load(merged_text) or {}
        result = persist_agent_document_with_ci(
            ctx.project_root, agent_id, document, ci_gate=payload.run_ci
        )
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "config": get_agent_config(ctx.project_root, agent_id)}


@router.post("/agents/{agent_id}/smoke")
async def agent_smoke_test(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    from forge_agent.spec.maturity import compute_maturity

    agent = load_agent_dict(ctx.project_root, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    spec = agent_dict_to_spec(agent)
    if not spec.mock_cases:
        raise HTTPException(status_code=400, detail="Agent has no mock_cases defined")
    smoke = await smoke_run_spec(spec)
    if smoke.get("success"):
        mark_smoke_verified(ctx.project_root, agent_id)
    updated = load_agent_dict(ctx.project_root, agent_id) or agent
    return {
        "success": bool(smoke.get("success")),
        "smoke": smoke,
        "maturity": compute_maturity(updated),
    }


class RunAgentPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents/{agent_id}/run")
async def run_agent(agent_id: str, body: RunAgentPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        return await run_single_agent(
            ctx.project_root, ctx.tenant_id, agent_id, body.payload, tenant=ctx.tenant
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agents/{agent_id}/run-defaults")
async def agent_run_defaults(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    agent = load_agent_dict(ctx.project_root, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return {"payload": default_run_payload(agent)}


class UpdateAgentPayload(BaseModel):
    yaml: str
    run_ci: bool = True


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, payload: UpdateAgentPayload, ctx: Ctx) -> dict[str, Any]:
    from forge_agent.spec.ci import CIGateError, persist_agent_document_with_ci

    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    try:
        document = yaml.safe_load(payload.yaml) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    try:
        result = persist_agent_document_with_ci(
            ctx.project_root, agent_id, document, ci_gate=payload.run_ci
        )
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, ctx: Ctx) -> Response:
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    target.unlink()
    return Response(status_code=204)
