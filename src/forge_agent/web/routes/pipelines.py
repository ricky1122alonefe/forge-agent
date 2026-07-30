"""Pipeline CRUD, presets, run routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from forge_agent.project.agent_builder import build_pipeline_yaml
from forge_agent.web.presets import PIPELINE_PRESETS, get_pipeline_preset
from forge_agent.web.routes._helpers import (
    Ctx,
    _ensure_agent_from_preset,
    _pipeline_path,
    _run_pipeline,
    collect_payload_fields,
    project_url,
)

router = APIRouter()


@router.get("/pipeline-presets")
async def list_pipeline_presets() -> dict[str, Any]:
    return {"presets": PIPELINE_PRESETS}


class CreatePipelineFromPresetPayload(BaseModel):
    preset_id: str


@router.post("/pipelines/from-preset")
async def create_pipeline_from_preset(
    payload: CreatePipelineFromPresetPayload, ctx: Ctx
) -> dict[str, Any]:
    preset = get_pipeline_preset(payload.preset_id)
    if preset is None:
        raise HTTPException(
            status_code=404, detail=f"Pipeline preset {payload.preset_id!r} not found"
        )

    agents_created: list[str] = []
    agent_ids: list[str] = []
    for agent_preset_id in preset.get("agent_presets", []):
        agent_id, created = await _ensure_agent_from_preset(agent_preset_id, ctx)
        agent_ids.append(agent_id)
        if created:
            agents_created.append(agent_id)

    if not agent_ids:
        raise HTTPException(status_code=400, detail="Pipeline preset has no valid agents")

    pipeline_id = preset["pipeline_id"]
    target = _pipeline_path(ctx.project_root, pipeline_id)
    pipeline_created = False
    if not target.exists():
        pipelines_dir = ctx.project_root / "pipelines"
        pipelines_dir.mkdir(exist_ok=True)
        yaml_text = build_pipeline_yaml(
            pipeline_id,
            preset["pipeline_name"],
            agent_ids,
            chief_id=preset.get("chief_id"),
            mode=preset.get("mode", "parallel"),
            description=preset.get("pipeline_description", preset.get("description", "")),
        )
        target.write_text(yaml_text, encoding="utf-8")
        pipeline_created = True

    return {
        "success": True,
        "preset_id": payload.preset_id,
        "pipeline_id": pipeline_id,
        "pipeline_name": preset["pipeline_name"],
        "agent_ids": agent_ids,
        "agents_created": agents_created,
        "pipeline_created": pipeline_created,
        "run_url": project_url(ctx.tenant_id, ctx.project_id, f"/pipelines/{pipeline_id}/run"),
        "workspace_url": project_url(ctx.tenant_id, ctx.project_id, "/"),
    }


class CreatePipelinePayload(BaseModel):
    pipeline_id: str
    name: str
    agent_ids: list[str]
    chief_id: str | None = None
    mode: str = "parallel"
    description: str = ""


@router.post("/pipelines")
async def create_pipeline(payload: CreatePipelinePayload, ctx: Ctx) -> dict[str, Any]:
    if not payload.agent_ids:
        raise HTTPException(status_code=400, detail="At least one agent must be selected")
    pipelines_dir = ctx.project_root / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)
    target = _pipeline_path(ctx.project_root, payload.pipeline_id)
    if target.exists():
        raise HTTPException(
            status_code=409, detail=f"Pipeline {payload.pipeline_id!r} already exists"
        )
    yaml_text = build_pipeline_yaml(
        payload.pipeline_id,
        payload.name,
        payload.agent_ids,
        chief_id=payload.chief_id,
        mode=payload.mode,
        description=payload.description,
    )
    target.write_text(yaml_text, encoding="utf-8")
    return {"success": True, "path": str(target), "pipeline_id": payload.pipeline_id}


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    target = _pipeline_path(ctx.project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    return {"pipeline_id": pipeline_id, "yaml": target.read_text(encoding="utf-8")}


class UpdatePipelinePayload(BaseModel):
    yaml: str


@router.put("/pipelines/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str, payload: UpdatePipelinePayload, ctx: Ctx
) -> dict[str, Any]:
    target = _pipeline_path(ctx.project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    try:
        yaml.safe_load(payload.yaml)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    target.write_text(payload.yaml, encoding="utf-8")
    return {"success": True, "pipeline_id": pipeline_id}


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, ctx: Ctx) -> Response:
    target = _pipeline_path(ctx.project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    target.unlink()
    return Response(status_code=204)


class RunPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, payload: RunPayload, ctx: Ctx) -> dict[str, Any]:
    pipeline_path = _pipeline_path(ctx.project_root, pipeline_id)
    if not pipeline_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    try:
        record = await _run_pipeline(
            ctx.project_root, ctx.tenant_id, pipeline_id, payload.payload, tenant=ctx.tenant
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "run_id": record.run_id, "record": record.to_dict()}


@router.get("/pipelines/{pipeline_id}/payload-fields")
async def get_pipeline_payload_fields(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    if not _pipeline_path(ctx.project_root, pipeline_id).exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    return {"fields": collect_payload_fields(ctx.project_root, pipeline_id)}
