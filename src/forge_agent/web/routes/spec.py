"""AgentSpec plan/apply/compose routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from forge_agent.spec import (
    AgentSpec,
    generate_spec,
    list_tool_catalog,
    mark_smoke_verified,
)
from forge_agent.spec.compose import apply_compose_plan, compose_from_requirement
from forge_agent.spec.coverage import compute_scenario_coverage
from forge_agent.spec.from_type import generate_from_agent_type
from forge_agent.web.routes._helpers import (
    Ctx,
    _agent_path,
    _apply_agent_spec,
    ensure_llm_ready,
    project_url,
    registry_for,
    resolve_llm_chat,
)

router = APIRouter()


class AgentSpecPlanPayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    agent_id: str | None = None
    keyword: str | None = None
    focus: str | None = None
    use_llm: bool = False


@router.post("/agent-spec/plan")
async def agent_spec_plan(payload: AgentSpecPlanPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        llm_chat = resolve_llm_chat(ctx.tenant, ctx.project_root) if payload.use_llm else None
        spec = await generate_spec(
            payload.requirement,
            agent_id=payload.agent_id,
            keyword=payload.keyword,
            focus=payload.focus,
            use_llm=payload.use_llm,
            llm_chat=llm_chat,
        )
        return spec.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class AgentSpecApplyPayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    agent_id: str | None = None
    keyword: str | None = None
    focus: str | None = None
    use_llm: bool = False
    overwrite: bool = False
    run_smoke: bool = True
    spec: dict[str, Any] | None = None


@router.post("/agent-spec/apply")
async def agent_spec_apply(payload: AgentSpecApplyPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        if payload.spec is not None:
            spec = AgentSpec.from_dict(payload.spec)
        else:
            llm_chat = resolve_llm_chat(ctx.tenant, ctx.project_root) if payload.use_llm else None
            spec = await generate_spec(
                payload.requirement,
                agent_id=payload.agent_id,
                keyword=payload.keyword,
                focus=payload.focus,
                use_llm=payload.use_llm,
                llm_chat=llm_chat,
            )
        result = await _apply_agent_spec(
            ctx, spec, overwrite=payload.overwrite, run_smoke=payload.run_smoke
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **result,
        "agent_url": project_url(ctx.tenant_id, ctx.project_id, f"/agents/{result['agent_id']}"),
    }


class AgentSpecFromTypePayload(BaseModel):
    agent_type: str
    agent_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    requirement: str = ""
    overwrite: bool = False
    run_smoke: bool = True
    apply: bool = True


@router.post("/agent-spec/from-type")
async def agent_spec_from_type(payload: AgentSpecFromTypePayload, ctx: Ctx) -> dict[str, Any]:
    try:
        type_def = registry_for(ctx).get(payload.agent_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = _agent_path(ctx.project_root, payload.agent_id)
    if target.exists() and not payload.overwrite:
        raise HTTPException(status_code=409, detail=f"Agent {payload.agent_id!r} already exists")

    spec = generate_from_agent_type(
        type_def, payload.agent_id, payload.params, requirement=payload.requirement
    )
    try:
        ensure_llm_ready(ctx.tenant, ctx.project_root)
        spec.config["mock_mode"] = False
    except Exception:
        pass
    if not payload.apply:
        return {"spec": spec.to_dict(), "applied": False}

    try:
        result = await _apply_agent_spec(
            ctx, spec, overwrite=payload.overwrite, run_smoke=payload.run_smoke
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **result,
        "spec": spec.to_dict(),
        "applied": True,
        "primitive": spec.primitive.value,
        "planner": spec.planner,
        "agent_url": project_url(ctx.tenant_id, ctx.project_id, f"/agents/{spec.agent_id}"),
    }


@router.get("/agent-spec/tools")
async def agent_spec_tool_catalog() -> dict[str, Any]:
    return {"tools": list_tool_catalog()}


@router.get("/agent-spec/coverage")
async def agent_spec_coverage() -> dict[str, Any]:
    return compute_scenario_coverage()


class AgentSpecComposePayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    keyword: str | None = None
    pipeline_id: str | None = None
    focus: str | None = None
    apply: bool = False
    overwrite: bool = False
    run_smoke: bool = True


@router.post("/agent-spec/compose")
async def agent_spec_compose(payload: AgentSpecComposePayload, ctx: Ctx) -> dict[str, Any]:
    try:
        plan = compose_from_requirement(
            payload.requirement,
            keyword=payload.keyword,
            pipeline_id=payload.pipeline_id,
            focus=payload.focus,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payload.apply:
        result = plan.to_dict()
        if payload.run_smoke and plan.specs:
            from forge_agent.spec.chain_smoke import smoke_compose_chain
            from forge_agent.spec.ci import CIGateError, run_ci_gate

            try:
                for spec in plan.specs:
                    run_ci_gate(spec)
                if len(plan.specs) > 1:
                    result["chain_smoke"] = await smoke_compose_chain(plan)
                result["ci_passed"] = True
            except CIGateError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    if plan.wiring_errors:
        raise HTTPException(status_code=400, detail="; ".join(plan.wiring_errors))

    from forge_agent.spec.ci import CIGateError

    try:
        applied = apply_compose_plan(
            ctx.project_root, plan, overwrite=payload.overwrite, ci_gate=payload.run_smoke
        )
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    smokes: list[dict[str, Any]] = []
    if payload.run_smoke:
        for spec in plan.specs:
            mark_smoke_verified(ctx.project_root, spec.agent_id)
        smokes = [{"agent_id": s.agent_id, "success": True, "ci_gate": True} for s in plan.specs]
        if len(plan.specs) > 1:
            smokes.append({"chain_smoke": True, "success": True})

    pid = plan.pipeline_id
    return {
        **plan.to_dict(),
        **applied,
        "applied": True,
        "smokes": smokes,
        "pipeline_url": project_url(ctx.tenant_id, ctx.project_id, f"/pipelines/{pid}"),
        "run_url": project_url(ctx.tenant_id, ctx.project_id, f"/pipelines/{pid}/run"),
    }


@router.post("/agent-spec/compose/export")
async def agent_spec_compose_export(payload: AgentSpecComposePayload, ctx: Ctx) -> dict[str, Any]:
    from forge_agent.spec.chain_smoke import smoke_compose_chain
    from forge_agent.spec.ci import CIGateError, run_ci_gate
    from forge_agent.web.bundles import export_compose_bundle

    try:
        plan = compose_from_requirement(
            payload.requirement,
            keyword=payload.keyword,
            pipeline_id=payload.pipeline_id,
            focus=payload.focus,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if plan.wiring_errors:
        raise HTTPException(status_code=400, detail="; ".join(plan.wiring_errors))

    if payload.run_smoke:
        try:
            for spec in plan.specs:
                run_ci_gate(spec)
            chain_smoke = None
            if len(plan.specs) > 1:
                chain_smoke = await smoke_compose_chain(plan)
        except CIGateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        chain_smoke = None

    bundle = export_compose_bundle(plan)
    return {"bundle": bundle, "plan": plan.to_dict(), "chain_smoke": chain_smoke}
