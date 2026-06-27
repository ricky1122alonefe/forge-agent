"""Page routes — HTML responses rendered via Jinja2 templates.

Mounted at root path by create_app().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from forge_agent.dashboard.data.code import CodeSource
from forge_agent.dashboard.data.manifest import load_manifest
from forge_agent.dashboard.data.traces import TraceDataSource

router = APIRouter()


def _get_templates() -> Jinja2Templates:
    templates_dir = Path(__file__).parent.parent / "templates"
    return Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Home page: agent list from MANIFEST."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root
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


@router.get("/agents/{agent_id}", response_class=HTMLResponse)
async def agent_detail(agent_id: str, request: Request) -> HTMLResponse:
    """Agent detail page: versions, traces, source code."""
    templates = _get_templates()
    project_root: Path = request.app.state.project_root

    # Load agent info from MANIFEST
    agents = load_manifest(project_root)
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    agent = agents[agent_id]

    # Load source code
    code_source = CodeSource(project_root)
    source_code = code_source.get_source(agent_id)

    # Load traces for this agent
    trace_source = TraceDataSource()
    traces = trace_source.get_traces_for_agent(agent_id, limit=10)

    return templates.TemplateResponse(
        request=request,
        name="agent_detail.html",
        context={
            "title": f"{agent_id} — forge-agent Dashboard",
            "agent": agent.to_dict(),
            "source_code": source_code,
            "traces": [t.to_dict() for t in traces],
        },
    )


@router.get("/traces", response_class=HTMLResponse)
async def traces_page(request: Request) -> HTMLResponse:
    """Traces list page."""
    templates = _get_templates()
    trace_source = TraceDataSource()
    traces = trace_source.list_traces(limit=50)
    return templates.TemplateResponse(
        request=request,
        name="traces.html",
        context={
            "title": "Traces — forge-agent Dashboard",
            "traces": [t.to_dict() for t in traces],
        },
    )


@router.get("/traces/{trace_id}", response_class=HTMLResponse)
async def trace_detail_page(trace_id: str, request: Request) -> HTMLResponse:
    """Trace detail page: spans timeline and attributes."""
    templates = _get_templates()
    trace_source = TraceDataSource()
    detail = trace_source.get_trace(trace_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id!r} not found")
    return templates.TemplateResponse(
        request=request,
        name="trace_detail.html",
        context={
            "title": f"Trace {trace_id} — forge-agent Dashboard",
            "trace": detail.to_dict(),
        },
    )


@router.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request) -> HTMLResponse:
    """Metrics dashboard page."""
    templates = _get_templates()
    from forge_agent.dashboard.data.metrics import MetricsDataSource
    metrics_source = MetricsDataSource()
    snapshot = metrics_source.snapshot()
    return templates.TemplateResponse(
        request=request,
        name="metrics.html",
        context={
            "title": "Metrics — forge-agent Dashboard",
            "metrics": snapshot.to_dict(),
        },
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request) -> HTMLResponse:
    """Reports history page."""
    templates = _get_templates()
    from forge_agent.dashboard.data.reports import ReportDataSource
    source = ReportDataSource()
    reports = source.list_reports(limit=50)
    summary = source.summary()
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "title": "Reports — forge-agent Dashboard",
            "reports": [r.to_dict() for r in reports],
            "summary": summary,
        },
    )
