"""Request-scoped tenant/project context for the web UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from forge_agent.exceptions import ProjectNotFoundError
from forge_agent.platform import LocalTenant
from forge_agent.web.auth.service import AuthUser
from forge_agent.web.llm_settings import bootstrap_project_secrets


@dataclass(frozen=True)
class ProjectContext:
    tenant: LocalTenant
    project_root: Path
    tenant_id: str
    project_id: str


def resolve_data_root(root_dir: Path | None = None) -> Path:
    """Resolve the forge-agent data root from env or explicit path."""
    return LocalTenant.resolve_data_root(root_dir)


def list_tenant_ids(data_root: Path) -> list[str]:
    """List tenant ids stored under a data root."""
    return LocalTenant.list_tenant_ids(data_root)


def project_url(tenant_id: str, project_id: str, path: str = "") -> str:
    """Build a project-scoped URL path."""
    base = f"/t/{tenant_id}/p/{project_id}"
    if not path or path == "/":
        return f"{base}/"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def tenant_url(tenant_id: str, path: str = "") -> str:
    """Build a tenant-scoped URL path."""
    base = f"/t/{tenant_id}"
    if not path or path == "/":
        return f"{base}/"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def get_project_context(tenant_id: str, project_id: str, request: Request) -> ProjectContext:
    """Resolve tenant + project from URL path parameters."""
    data_root: Path = request.app.state.data_root
    tenant = LocalTenant(tenant_id, root_dir=data_root)
    try:
        project_root = tenant.get_project_path(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    bootstrap_project_secrets(tenant, project_root)
    return ProjectContext(
        tenant=tenant,
        project_root=project_root,
        tenant_id=tenant_id,
        project_id=project_id,
    )


def base_context(request: Request, ctx: ProjectContext) -> dict:
    """Shared Jinja context for project-scoped pages."""

    def pu(path: str = "/") -> str:
        return project_url(ctx.tenant_id, ctx.project_id, path)

    auth_config = getattr(request.app.state, "auth_config", None)
    auth_enabled = bool(auth_config and auth_config.enabled)
    auth_user: AuthUser | None = getattr(request.state, "user", None)

    from forge_agent.web.llm_settings import get_llm_settings_view

    llm_settings = get_llm_settings_view(ctx.tenant, ctx.project_id)

    return {
        "request": request,
        "tenant_id": ctx.tenant_id,
        "project_id": ctx.project_id,
        "pu": pu,
        "api_prefix": project_url(ctx.tenant_id, ctx.project_id, "/api"),
        "tenant_hub_url": tenant_url(ctx.tenant_id),
        "auth_enabled": auth_enabled,
        "auth_user": auth_user,
        "llm_settings": llm_settings,
    }
