"""Page routes for the self-hosted web UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from forge_agent.agent_spec.maturity import compute_maturity
from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project.state_store import StateStore
from forge_agent.web.bundles import build_market_catalog
from forge_agent.web.context import ProjectContext, base_context, get_project_context
from forge_agent.web.data import (
    collect_payload_fields,
    extract_chief_report,
    format_trace_timeline,
    get_agent,
    get_agent_config,
    get_pipeline_run_plan,
    infer_run_mock_mode,
    list_agents,
    list_pipelines,
    load_run_trace,
    summarize_pipeline_mock_mode,
    summarize_project_mock_mode,
)
from forge_agent.web.llm_settings import get_llm_settings_view, load_env_files
from forge_agent.web.presets import AGENT_PRESETS, PIPELINE_PRESETS, template_label

router = APIRouter()
Ctx = Annotated[ProjectContext, Depends(get_project_context)]


def _get_templates() -> Jinja2Templates:
    templates_dir = Path(__file__).parent.parent / "templates"
    return Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, ctx: Ctx) -> HTMLResponse:
    """Home page: overview of agents, pipelines, and recent runs."""
    templates = _get_templates()
    project_root = ctx.project_root
    agents = list_agents(project_root)
    pipelines = list_pipelines(project_root)
    runs = StateStore(project_root).list()[:10]
    mock_summary = summarize_project_mock_mode(project_root)
    context = base_context(request, ctx)
    context.update(
        {
            "agents": [
                {
                    **agent,
                    "mock_mode": get_agent_config(project_root, agent["agent_id"])["mock_mode"],
                }
                for agent in agents
            ],
            "pipelines": pipelines,
            "runs": [r.to_dict() for r in runs],
            "is_empty_project": not agents and not pipelines,
            "needs_pipeline": bool(agents) and not pipelines,
            "needs_first_run": bool(pipelines) and not runs,
            "agent_presets": AGENT_PRESETS,
            "pipeline_presets": PIPELINE_PRESETS,
            "mock_summary": mock_summary,
            "show_mock_notice": mock_summary["any_mock"],
        }
    )
    return templates.TemplateResponse(request=request, name="index.html", context=context)


@router.get("/agents/new", response_class=HTMLResponse)
async def create_agent_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """Create agent form."""
    templates = _get_templates()
    registry = AgentTypeRegistry(tenant_shared_dir=ctx.tenant.get_shared_path())
    types = registry.list()
    context = base_context(request, ctx)
    context.update(
        {
            "types": types,
            "types_json": json.dumps(types, ensure_ascii=False),
            "type_labels": {
                t["type_id"]: template_label(t["type_id"], t.get("name", t["type_id"]))
                for t in types
            },
            "agent_presets": AGENT_PRESETS,
            "edit_mode": False,
        }
    )
    return templates.TemplateResponse(request=request, name="create_agent.html", context=context)


@router.get("/agents/generate", response_class=HTMLResponse)
async def generate_agent_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """Natural-language Agent generator (AGENT_PLAN A3.1)."""
    templates = _get_templates()
    context = base_context(request, ctx)
    context.update(
        {
            "examples": [
                "分析 labubu 在微博的热度趋势",
                "搜索 AI 行业动态并给出趋势判断",
                "汇总上游多份 Agent 报告并给出综合结论",
                "当库存低于阈值 100 时告警",
                "润色并改写营销报告",
                "对用户评论做情感分类",
            ],
        }
    )
    return templates.TemplateResponse(request=request, name="generate_agent.html", context=context)


@router.get("/agents/{agent_id}", response_class=HTMLResponse)
async def agent_detail_page(agent_id: str, request: Request, ctx: Ctx) -> HTMLResponse:
    """View / edit agent page."""
    templates = _get_templates()
    agent_file = ctx.project_root / "agents" / f"{agent_id}.yaml"
    if not agent_file.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    agent = get_agent(ctx.project_root, agent_id) or {}
    context = base_context(request, ctx)
    context.update(
        {
            "agent_id": agent_id,
            "yaml": agent_file.read_text(encoding="utf-8"),
            "agent_config": get_agent_config(ctx.project_root, agent_id),
            "maturity": compute_maturity(agent),
        }
    )
    return templates.TemplateResponse(request=request, name="agent_detail.html", context=context)


@router.get("/pipelines/new", response_class=HTMLResponse)
async def create_pipeline_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """Create pipeline form."""
    templates = _get_templates()
    context = base_context(request, ctx)
    context.update(
        {
            "agents": list_agents(ctx.project_root),
            "edit_mode": False,
            "pipeline_presets": PIPELINE_PRESETS,
        }
    )
    return templates.TemplateResponse(request=request, name="create_pipeline.html", context=context)


@router.get("/pipelines/{pipeline_id}", response_class=HTMLResponse)
async def pipeline_detail_page(pipeline_id: str, request: Request, ctx: Ctx) -> HTMLResponse:
    """View / edit pipeline page."""
    templates = _get_templates()
    pipeline_file = ctx.project_root / "pipelines" / f"{pipeline_id}.yaml"
    if not pipeline_file.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    context = base_context(request, ctx)
    context.update(
        {
            "pipeline_id": pipeline_id,
            "yaml": pipeline_file.read_text(encoding="utf-8"),
        }
    )
    return templates.TemplateResponse(request=request, name="pipeline_detail.html", context=context)


@router.get("/pipelines/{pipeline_id}/run", response_class=HTMLResponse)
async def run_pipeline_page(pipeline_id: str, request: Request, ctx: Ctx) -> HTMLResponse:
    """Run pipeline form."""
    templates = _get_templates()
    pipeline_path = ctx.project_root / "pipelines" / f"{pipeline_id}.yaml"
    if not pipeline_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    mock_summary = summarize_pipeline_mock_mode(ctx.project_root, pipeline_id)
    run_plan = get_pipeline_run_plan(ctx.project_root, pipeline_id)
    context = base_context(request, ctx)
    context.update(
        {
            "pipeline_id": pipeline_id,
            "payload_fields": collect_payload_fields(ctx.project_root, pipeline_id),
            "run_plan": run_plan,
            "mock_summary": mock_summary,
            "show_mock_notice": mock_summary["all_mock"],
            "run_plan_json": json.dumps(run_plan, ensure_ascii=False),
        }
    )
    return templates.TemplateResponse(request=request, name="run_pipeline.html", context=context)


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """Run history page."""
    templates = _get_templates()
    runs = StateStore(ctx.project_root).list()
    context = base_context(request, ctx)
    context.update(
        {
            "runs": [
                {
                    **r.to_dict(),
                    "is_mock": r.metadata.get("mock_mode", infer_run_mock_mode(r.agent_reports)),
                }
                for r in runs
            ],
        }
    )
    return templates.TemplateResponse(request=request, name="runs.html", context=context)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_page(run_id: str, request: Request, ctx: Ctx) -> HTMLResponse:
    """Run detail page."""
    templates = _get_templates()
    record = StateStore(ctx.project_root).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    chief = extract_chief_report(record.chief_summary)
    run_mock = record.metadata.get("mock_mode")
    if run_mock is None:
        run_mock = infer_run_mock_mode(record.agent_reports)
    trace_data = load_run_trace(ctx.project_root, record.trace_id)
    trace_timeline = format_trace_timeline(trace_data)
    context = base_context(request, ctx)
    context.update(
        {
            "run": record.to_dict(),
            "payload_json": json.dumps(record.payload, ensure_ascii=False, indent=2),
            "agent_reports": record.agent_reports,
            "chief_report": chief,
            "reports_json": json.dumps(record.agent_reports, ensure_ascii=False, indent=2),
            "chief_json": json.dumps(record.chief_summary, ensure_ascii=False, indent=2),
            "show_mock_notice": bool(run_mock),
            "run_mock_mode": bool(run_mock),
            "trace_id": record.trace_id,
            "duration_ms": record.metadata.get("duration_ms"),
            "trace_timeline": trace_timeline,
        }
    )
    return templates.TemplateResponse(request=request, name="run_detail.html", context=context)


@router.get("/settings/llm", response_class=HTMLResponse)
async def llm_settings_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """LLM provider and API key settings (P3.3)."""
    templates = _get_templates()
    load_env_files(ctx.tenant, ctx.project_root)
    context = base_context(request, ctx)
    context.update({"settings": get_llm_settings_view(ctx.tenant, ctx.project_id)})
    return templates.TemplateResponse(request=request, name="llm_settings.html", context=context)


@router.get("/market", response_class=HTMLResponse)
async def market_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """Template market: presets, shared bundles, import/export (Phase 4)."""
    templates = _get_templates()
    shared_market = ctx.tenant.get_shared_path() / "market"
    context = base_context(request, ctx)
    context.update(
        {
            "catalog": build_market_catalog(ctx.project_root, shared_market),
            "agent_presets": AGENT_PRESETS,
            "pipeline_presets": PIPELINE_PRESETS,
        }
    )
    return templates.TemplateResponse(request=request, name="market.html", context=context)


@router.get("/architect", response_class=HTMLResponse)
async def architect_page(request: Request, ctx: Ctx) -> HTMLResponse:
    """Natural-language pipeline architect (P4.4)."""
    templates = _get_templates()
    context = base_context(request, ctx)
    return templates.TemplateResponse(request=request, name="architect.html", context=context)
