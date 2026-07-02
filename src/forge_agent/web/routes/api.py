"""API routes for the self-hosted web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project.agent_builder import build_agent_yaml, build_pipeline_yaml
from forge_agent.project.launcher import _run_pipeline

router = APIRouter(prefix="/api")


@router.get("/agent-types")
async def get_agent_types(request: Request) -> dict[str, Any]:
    """List available agent types."""
    tenant = request.app.state.tenant
    registry = AgentTypeRegistry(tenant_shared_dir=tenant.get_shared_path())
    return {"types": registry.list()}


class CreateAgentPayload(BaseModel):
    agent_type: str
    agent_id: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents")
async def create_agent(payload: CreateAgentPayload, request: Request) -> dict[str, Any]:
    """Create a new agent YAML file from a selected agent type."""
    project_root: Path = request.app.state.project_root
    tenant = request.app.state.tenant
    registry = AgentTypeRegistry(tenant_shared_dir=tenant.get_shared_path())

    try:
        type_def = registry.get(payload.agent_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agents_dir = project_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    target = agents_dir / f"{payload.agent_id}.yaml"
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Agent {payload.agent_id!r} already exists")

    yaml_text = build_agent_yaml(type_def, payload.agent_id, payload.params)
    target.write_text(yaml_text, encoding="utf-8")
    return {"success": True, "path": str(target)}


class CreatePipelinePayload(BaseModel):
    pipeline_id: str
    name: str
    agent_ids: list[str]
    chief_id: str | None = None
    description: str = ""


@router.post("/pipelines")
async def create_pipeline(payload: CreatePipelinePayload, request: Request) -> dict[str, Any]:
    """Create a new pipeline YAML file."""
    project_root: Path = request.app.state.project_root
    if not payload.agent_ids:
        raise HTTPException(status_code=400, detail="At least one agent must be selected")

    pipelines_dir = project_root / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)
    target = pipelines_dir / f"{payload.pipeline_id}.yaml"
    if target.exists():
        raise HTTPException(
            status_code=409, detail=f"Pipeline {payload.pipeline_id!r} already exists"
        )

    yaml_text = build_pipeline_yaml(
        payload.pipeline_id,
        payload.name,
        payload.agent_ids,
        chief_id=payload.chief_id,
        description=payload.description,
    )
    target.write_text(yaml_text, encoding="utf-8")
    return {"success": True, "path": str(target)}


class RunPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, payload: RunPayload, request: Request) -> dict[str, Any]:
    """Run a pipeline and return the resulting run record."""
    project_root: Path = request.app.state.project_root
    tenant_id: str = request.app.state.tenant.tenant_id
    pipeline_path = project_root / "pipelines" / f"{pipeline_id}.yaml"
    if not pipeline_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")

    try:
        record = await _run_pipeline(project_root, tenant_id, pipeline_id, payload.payload)
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {"success": True, "run_id": record.run_id, "record": record.to_dict()}
