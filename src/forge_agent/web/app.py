"""FastAPI application factory for the self-hosted web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from forge_agent.web.auth.config import WebAuthConfig
from forge_agent.web.auth.middleware import WebAuthMiddleware
from forge_agent.web.auth.routes import router as auth_router
from forge_agent.web.context import resolve_data_root
from forge_agent.web.routes import api, hub, pages


def create_app(
    *,
    data_root: Path | None = None,
    default_tenant_id: str = "default",
    default_project_id: str = "default",
    auth_config: WebAuthConfig | None = None,
) -> FastAPI:
    """Create the forge-agent web application.

    Args:
        data_root: Optional override for the forge-agent data directory.
        default_tenant_id: Tenant used for ``/`` redirect when auth is disabled.
        default_project_id: Project used for ``/`` redirect when auth is disabled.
        auth_config: Optional auth configuration. Defaults to env ``FORGE_AGENT_WEB_AUTH``.
    """
    app = FastAPI(title="forge-agent", version="0.3.0")

    app.state.data_root = resolve_data_root(data_root)
    app.state.default_tenant_id = default_tenant_id
    app.state.default_project_id = default_project_id
    app.state.auth_config = auth_config or WebAuthConfig.from_env()

    if app.state.auth_config.enabled:
        app.add_middleware(WebAuthMiddleware, auth_config=app.state.auth_config)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth_router)
    app.include_router(hub.router)
    app.include_router(pages.router, prefix="/t/{tenant_id}/p/{project_id}")
    app.include_router(api.router, prefix="/t/{tenant_id}/p/{project_id}")

    return app
