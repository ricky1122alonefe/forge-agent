"""FastAPI application factory for the dashboard.

Architecture:
    create_app() → mounts route modules (pages, api, ws)
    Route modules → use data layer (data/*.py)
    Data layer → wraps core modules (manifest, trace, metrics, store)

This keeps app.py as a thin composition layer.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from forge_agent.dashboard.auth import AuthConfig, AuthMiddleware
from forge_agent.dashboard.routes.api import router as api_router
from forge_agent.dashboard.routes.pages import router as pages_router
from forge_agent.dashboard.routes.ws import router as ws_router


def create_app(
    project_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    auth_config: AuthConfig | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        project_root: Root directory of the forge-agent project
        host: Bind host (default: 127.0.0.1)
        port: Bind port (default: 8765)
        auth_config: Optional authentication configuration

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="forge-agent Dashboard",
        description="Local observability dashboard for forge-agent",
        version="0.3.0",
    )

    # Store config in app state (accessible by routes via request.app.state)
    app.state.project_root = project_root
    app.state.host = host
    app.state.port = port

    # Authentication middleware
    if auth_config and auth_config.enabled:
        app.add_middleware(AuthMiddleware, auth_config=auth_config)

    # Static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Mount route modules
    app.include_router(pages_router)
    app.include_router(api_router)
    app.include_router(ws_router, prefix="/ws")

    return app
