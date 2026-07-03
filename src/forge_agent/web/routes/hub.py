"""Tenant and project hub routes (no active project required)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from forge_agent.exceptions import ProjectAlreadyExistsError
from forge_agent.platform import LocalTenant
from forge_agent.web.context import list_tenant_ids, project_url, tenant_url

router = APIRouter()


def _get_templates():
    from fastapi.templating import Jinja2Templates

    templates_dir = Path(__file__).parent.parent / "templates"
    return Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=RedirectResponse)
async def root_redirect(request: Request) -> RedirectResponse:
    """Redirect to the default tenant/project workspace."""
    tenant_id: str = request.app.state.default_tenant_id
    project_id: str = request.app.state.default_project_id
    return RedirectResponse(
        url=project_url(tenant_id, project_id, "/"),
        status_code=302,
    )


@router.get("/t/{tenant_id}/", response_class=HTMLResponse)
async def tenant_hub_page(tenant_id: str, request: Request) -> HTMLResponse:
    """List projects for a tenant and allow creating new ones."""
    templates = _get_templates()
    data_root: Path = request.app.state.data_root
    tenant = LocalTenant(tenant_id, root_dir=data_root)
    tenant.get_shared_path()
    projects = tenant.list_projects()
    context = {
        "request": request,
        "tenant_id": tenant_id,
        "projects": projects,
        "project_link": lambda project_id: project_url(tenant_id, project_id, "/"),
        "tenant_api_prefix": tenant_url(tenant_id, "/api"),
    }
    return templates.TemplateResponse(request=request, name="tenant_hub.html", context=context)


class CreateProjectPayload(BaseModel):
    project_id: str
    name: str = ""


@router.get("/t/{tenant_id}/api/projects")
async def list_projects_api(tenant_id: str, request: Request) -> dict[str, Any]:
    """List projects for a tenant."""
    data_root: Path = request.app.state.data_root
    tenant = LocalTenant(tenant_id, root_dir=data_root)
    return {"tenant_id": tenant_id, "projects": tenant.list_projects()}


@router.post("/t/{tenant_id}/api/projects")
async def create_project_api(
    tenant_id: str, payload: CreateProjectPayload, request: Request
) -> dict[str, Any]:
    """Create a new project under a tenant."""
    data_root: Path = request.app.state.data_root
    tenant = LocalTenant(tenant_id, root_dir=data_root)
    project_id = payload.project_id.strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    try:
        project_root = tenant.create_project(project_id)
    except ProjectAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "success": True,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "project_root": str(project_root),
        "url": project_url(tenant_id, project_id, "/"),
    }


@router.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    """Health check and basic deployment info."""
    data_root: Path = request.app.state.data_root
    return {
        "status": "ok",
        "data_root": str(data_root),
        "default_tenant_id": request.app.state.default_tenant_id,
        "default_project_id": request.app.state.default_project_id,
        "tenants": list_tenant_ids(data_root),
    }
