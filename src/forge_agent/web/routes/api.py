"""API routes for the self-hosted web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project.agent_builder import build_agent_yaml, build_pipeline_yaml
from forge_agent.project.launcher import _run_pipeline

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Health check and basic tenant/project info."""
    return {
        "status": "ok",
        "tenant_id": request.app.state.tenant.tenant_id,
        "project_root": str(request.app.state.project_root),
    }


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


def _agent_path(project_root: Path, agent_id: str) -> Path:
    return project_root / "agents" / f"{agent_id}.yaml"


def _pipeline_path(project_root: Path, pipeline_id: str) -> Path:
    return project_root / "pipelines" / f"{pipeline_id}.yaml"


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
    target = _agent_path(project_root, payload.agent_id)
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Agent {payload.agent_id!r} already exists")

    yaml_text = build_agent_yaml(type_def, payload.agent_id, payload.params)
    target.write_text(yaml_text, encoding="utf-8")
    return {"success": True, "path": str(target), "agent_id": payload.agent_id}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request) -> dict[str, Any]:
    """Return the raw YAML content of an agent."""
    project_root: Path = request.app.state.project_root
    target = _agent_path(project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return {"agent_id": agent_id, "yaml": target.read_text(encoding="utf-8")}


class UpdateAgentPayload(BaseModel):
    yaml: str


@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: str, payload: UpdateAgentPayload, request: Request
) -> dict[str, Any]:
    """Overwrite an agent YAML file."""
    project_root: Path = request.app.state.project_root
    target = _agent_path(project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    try:
        yaml.safe_load(payload.yaml)  # validate yaml syntax
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    target.write_text(payload.yaml, encoding="utf-8")
    return {"success": True, "agent_id": agent_id}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, request: Request) -> Response:
    """Delete an agent YAML file."""
    project_root: Path = request.app.state.project_root
    target = _agent_path(project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    target.unlink()
    return Response(status_code=204)


class CreatePipelinePayload(BaseModel):
    pipeline_id: str
    name: str
    agent_ids: list[str]
    chief_id: str | None = None
    mode: str = "parallel"
    description: str = ""


@router.post("/pipelines")
async def create_pipeline(payload: CreatePipelinePayload, request: Request) -> dict[str, Any]:
    """Create a new pipeline YAML file."""
    project_root: Path = request.app.state.project_root
    if not payload.agent_ids:
        raise HTTPException(status_code=400, detail="At least one agent must be selected")

    pipelines_dir = project_root / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)
    target = _pipeline_path(project_root, payload.pipeline_id)
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
async def get_pipeline(pipeline_id: str, request: Request) -> dict[str, Any]:
    """Return the raw YAML content of a pipeline."""
    project_root: Path = request.app.state.project_root
    target = _pipeline_path(project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    return {"pipeline_id": pipeline_id, "yaml": target.read_text(encoding="utf-8")}


class UpdatePipelinePayload(BaseModel):
    yaml: str


@router.put("/pipelines/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str, payload: UpdatePipelinePayload, request: Request
) -> dict[str, Any]:
    """Overwrite a pipeline YAML file."""
    project_root: Path = request.app.state.project_root
    target = _pipeline_path(project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    try:
        yaml.safe_load(payload.yaml)  # validate yaml syntax
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    target.write_text(payload.yaml, encoding="utf-8")
    return {"success": True, "pipeline_id": pipeline_id}


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, request: Request) -> Response:
    """Delete a pipeline YAML file."""
    project_root: Path = request.app.state.project_root
    target = _pipeline_path(project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    target.unlink()
    return Response(status_code=204)


class RunPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, payload: RunPayload, request: Request) -> dict[str, Any]:
    """Run a pipeline and return the resulting run record."""
    project_root: Path = request.app.state.project_root
    tenant_id: str = request.app.state.tenant.tenant_id
    pipeline_path = _pipeline_path(project_root, pipeline_id)
    if not pipeline_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")

    try:
        record = await _run_pipeline(project_root, tenant_id, pipeline_id, payload.payload)
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {"success": True, "run_id": record.run_id, "record": record.to_dict()}
