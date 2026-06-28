"""API routes — JSON responses for programmatic access.

Mounted at /api prefix by create_app().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from forge_agent.dashboard.data.manifest import load_manifest
from forge_agent.dashboard.data.traces import TraceDataSource

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@router.get("/agents")
async def list_agents(request: Request) -> dict[str, Any]:
    """List all agents from MANIFEST.json."""
    project_root: Path = request.app.state.project_root
    agents = load_manifest(project_root)
    return {
        "agents": {aid: info.to_dict() for aid, info in agents.items()},
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request) -> dict[str, Any]:
    """Get a single agent's full info."""
    project_root: Path = request.app.state.project_root
    agents = load_manifest(project_root)
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return agents[agent_id].to_dict()


@router.get("/agents/{agent_id}/source")
async def get_agent_source(
    agent_id: str,
    request: Request,
    version: str | None = None,
) -> dict[str, Any]:
    """Get source code for an agent."""
    project_root: Path = request.app.state.project_root
    from forge_agent.dashboard.data.code import CodeSource

    code_source = CodeSource(project_root)
    source = code_source.get_source(agent_id, version)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source for {agent_id!r} not found")
    return {"agent_id": agent_id, "version": version or "active", "source": source}


@router.get("/traces")
async def list_traces(limit: int = 50) -> dict[str, Any]:
    """List recent traces."""
    trace_source = TraceDataSource()
    traces = trace_source.list_traces(limit=limit)
    return {"traces": [t.to_dict() for t in traces]}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    """Get full trace detail."""
    trace_source = TraceDataSource()
    detail = trace_source.get_trace(trace_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id!r} not found")
    return detail.to_dict()


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Get current metrics snapshot."""
    from forge_agent.dashboard.data.metrics import MetricsDataSource

    metrics_source = MetricsDataSource()
    snapshot = metrics_source.snapshot()
    return snapshot.to_dict()


@router.get("/reports")
async def list_reports(
    agent_id: str | None = None,
    domain: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List recent agent reports."""
    from forge_agent.dashboard.data.reports import ReportDataSource

    source = ReportDataSource()
    reports = source.list_reports(agent_id=agent_id, domain=domain, limit=limit)
    return {"reports": [r.to_dict() for r in reports]}


@router.get("/reports/summary")
async def get_report_summary(
    agent_id: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Get aggregate report statistics."""
    from forge_agent.dashboard.data.reports import ReportDataSource

    source = ReportDataSource()
    return source.summary(agent_id=agent_id, domain=domain)


@router.get("/reports/{run_id}")
async def get_report(run_id: str) -> dict[str, Any]:
    """Get full report detail by run_id."""
    from forge_agent.dashboard.data.reports import ReportDataSource

    source = ReportDataSource()
    detail = source.get_report(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Report {run_id!r} not found")
    return detail.to_dict()


@router.get("/presets")
async def list_presets() -> dict[str, Any]:
    """List all available domain presets for scraper agents."""
    from forge_agent.scraper.presets import list_presets as _list_presets

    return {"presets": _list_presets()}


@router.get("/presets/{domain}")
async def get_preset(domain: str) -> dict[str, Any]:
    """Get a single domain preset by name."""
    from forge_agent.scraper.presets import get_preset as _get_preset

    preset = _get_preset(domain)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Preset {domain!r} not found")
    return preset.to_dict()


@router.get("/data")
async def list_data(
    agent_id: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List stored data records (all agent types)."""
    from forge_agent.storage import ForgeStore

    store = ForgeStore()
    records = store.query(agent_id=agent_id, category=category, limit=limit, offset=offset)
    summary = store.summary(agent_id=agent_id)
    return {
        "records": [r.to_dict() for r in records],
        "summary": summary,
    }


@router.get("/data/agents")
async def list_data_agents() -> dict[str, Any]:
    """List all agents that have stored data."""
    from forge_agent.storage import ForgeStore

    store = ForgeStore()
    return {"agents": store.list_agents()}


@router.get("/data/{agent_id}")
async def get_agent_data(
    agent_id: str,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Get stored data for a specific agent."""
    from forge_agent.storage import ForgeStore

    store = ForgeStore()
    records = store.query(
        agent_id=agent_id,
        category=category,
        limit=limit,
        offset=offset,
        start_time=start_time,
        end_time=end_time,
    )
    summary = store.summary(agent_id=agent_id)
    return {
        "agent_id": agent_id,
        "records": [r.to_dict() for r in records],
        "summary": summary,
    }


@router.get("/data/{agent_id}/timeseries")
async def get_timeseries(
    agent_id: str,
    field_name: str,
    category: str | None = None,
    limit: int = 500,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Get time-series data for a specific field of an agent."""
    from forge_agent.storage import ForgeStore

    store = ForgeStore()
    series = store.get_time_series(
        agent_id=agent_id,
        field_name=field_name,
        category=category,
        limit=limit,
        start_time=start_time,
        end_time=end_time,
    )
    return {"agent_id": agent_id, "field": field_name, "series": series}


@router.delete("/data/{agent_id}")
async def delete_agent_data(
    agent_id: str,
    before: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Delete stored data for an agent."""
    from forge_agent.storage import ForgeStore

    store = ForgeStore()
    deleted = store.delete(agent_id=agent_id, before=before, category=category)
    return {"agent_id": agent_id, "deleted": deleted}


@router.post("/generate")
async def generate_agent(request: Request) -> dict[str, Any]:
    """Generate a new agent from the dashboard form."""
    body = await request.json()
    requirement = body.get("requirement", "")
    agent_id = body.get("agent_id", "")
    name = body.get("name", "")
    domain = body.get("domain", "generic")
    agent_type = body.get("agent_type", "general")
    provider_name = body.get("provider")
    deploy_mode_str = body.get("deploy_mode", "manual_review")

    if not requirement:
        return {"success": False, "error": "requirement is required"}
    if not agent_id:
        return {"success": False, "error": "agent_id is required"}

    try:
        from forge_agent.generator.pipeline import DeployMode, GenerationPipeline
        from forge_agent.generator.store import FileCodeStore
        from forge_agent.llm import chat, list_providers

        project_root: Path = request.app.state.project_root
        code_store = FileCodeStore(str(project_root / "generated_agents"))
        deploy_mode = DeployMode(deploy_mode_str)

        # Pick provider
        provider = provider_name
        if not provider:
            available = list_providers()
            if not available:
                return {
                    "success": False,
                    "error": "No LLM providers configured. Set $DEEPSEEK_API_KEY or create llm_providers.json.",
                }
            provider = available[0]

        async def _chat(messages, **kwargs):
            return await chat(messages, provider=provider, **kwargs)

        pipeline = GenerationPipeline(
            llm_chat=_chat,
            code_store=code_store,
        )

        # Enrich requirement with structured info
        full_requirement = f"{requirement}\n\nAgent ID: {agent_id}\nName: {name}\nDomain: {domain}\nType: {agent_type}"

        result = await pipeline.generate_and_deploy(
            requirement=full_requirement,
            deploy_mode=deploy_mode,
            agent_id=agent_id,
        )

        return {
            "success": result.success,
            "agent_id": result.agent_id,
            "deployed": result.deployed,
            "code_path": result.code_path,
            "attempts": 1,
            "error": None if result.success else "Generation failed — check validation results",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
