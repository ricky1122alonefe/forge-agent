"""FastAPI application factory for the self-hosted web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from forge_agent.platform import LocalTenant
from forge_agent.web.routes import api, pages


def create_app(tenant: LocalTenant, project_root: Path) -> FastAPI:
    """Create the forge-agent web application.

    Args:
        tenant: The tenant that owns the project.
        project_root: Root directory of the active project.

    Returns:
        A configured FastAPI application.
    """
    app = FastAPI(title="forge-agent", version="0.3.0")

    app.state.tenant = tenant
    app.state.project_root = project_root

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(pages.router)
    app.include_router(api.router)

    return app
