"""Page routes for the self-hosted web UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project.state_store import StateStore
from forge_agent.web.data import list_agents, list_pipelines

router = APIRouter()


def _get_templates() -> Jinja2Templates:
    templates_dir = Path(__file__).parent.parent / "templates"
    return Jinja2Templates(directory=str(templates_dir))


def _base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "tenant_id": request.app.state.tenant.tenant_id,
        "project_id": request.app.state.project_root.name,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Home page: overview of agents, pipelines, and recent runs."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root
    runs = StateStore(project_root).list()[:10]
    context = _base_context(request)
    context.update(
        {
            "agents": list_agents(project_root),
            "pipelines": list_pipelines(project_root),
            "runs": [r.to_dict() for r in runs],
        }
    )
    return templates.TemplateResponse(request=request, name="index.html", context=context)


@router.get("/agents/new", response_class=HTMLResponse)
async def create_agent_page(request: Request) -> HTMLResponse:
    """Create agent form."""
    templates = _get_templates()
    tenant = request.app.state.tenant
    registry = AgentTypeRegistry(tenant_shared_dir=tenant.get_shared_path())
    context = _base_context(request)
    context.update(
        {
            "types": registry.list(),
            "types_json": json.dumps(registry.list(), ensure_ascii=False),
        }
    )
    return templates.TemplateResponse(request=request, name="create_agent.html", context=context)


@router.get("/pipelines/new", response_class=HTMLResponse)
async def create_pipeline_page(request: Request) -> HTMLResponse:
    """Create pipeline form."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root
    context = _base_context(request)
    context.update({"agents": list_agents(project_root)})
    return templates.TemplateResponse(request=request, name="create_pipeline.html", context=context)


@router.get("/pipelines/{pipeline_id}/run", response_class=HTMLResponse)
async def run_pipeline_page(pipeline_id: str, request: Request) -> HTMLResponse:
    """Run pipeline form."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root
    pipeline_path = project_root / "pipelines" / f"{pipeline_id}.yaml"
    if not pipeline_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    context = _base_context(request)
    context.update({"pipeline_id": pipeline_id})
    return templates.TemplateResponse(request=request, name="run_pipeline.html", context=context)


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request) -> HTMLResponse:
    """Run history page."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root
    runs = StateStore(project_root).list()
    context = _base_context(request)
    context.update({"runs": [r.to_dict() for r in runs]})
    return templates.TemplateResponse(request=request, name="runs.html", context=context)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_page(run_id: str, request: Request) -> HTMLResponse:
    """Run detail page."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root
    record = StateStore(project_root).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    context = _base_context(request)
    context.update(
        {
            "run": record.to_dict(),
            "payload_json": json.dumps(record.payload, ensure_ascii=False, indent=2),
            "reports_json": json.dumps(record.agent_reports, ensure_ascii=False, indent=2),
            "chief_json": json.dumps(record.chief_summary, ensure_ascii=False, indent=2),
        }
    )
    return templates.TemplateResponse(request=request, name="run_detail.html", context=context)
