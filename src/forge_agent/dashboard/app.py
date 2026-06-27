"""FastAPI application factory for the dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from forge_agent.dashboard.data.manifest import load_manifest


def create_app(
    project_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        project_root: Root directory of the forge-agent project
        host: Bind host (default: 127.0.0.1)
        port: Bind port (default: 8765)

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="forge-agent Dashboard",
        description="Local observability dashboard for forge-agent",
        version="0.3.0",
    )

    # Store project root in app state
    app.state.project_root = project_root
    app.state.host = host
    app.state.port = port

    # Setup templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Setup static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ---- Health check ----

    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    # ---- Pages (HTML) ----

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request) -> HTMLResponse:
        """Serve the main dashboard page with agent list from MANIFEST."""
        agents = load_manifest(project_root)
        agent_list = [info.to_dict() for info in agents.values()]
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "title": "forge-agent Dashboard",
                "agents": agent_list,
                "total_agents": len(agent_list),
                "total_versions": sum(a.version_count for a in agents.values()),
            },
        )

    # ---- REST API (JSON) ----

    @app.get("/api/agents")
    async def list_agents(request: Request) -> dict[str, Any]:
        """List all agents from MANIFEST.json."""
        project_root: Path = request.app.state.project_root
        agents = load_manifest(project_root)
        return {
            "agents": {aid: info.to_dict() for aid, info in agents.items()},
        }

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str, request: Request) -> dict[str, Any]:
        """Get a single agent's full info."""
        project_root: Path = request.app.state.project_root
        agents = load_manifest(project_root)
        if agent_id not in agents:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
        return agents[agent_id].to_dict()

    return app
