"""Architect plan/apply routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from forge_agent.web.architect import apply_plan, generate_plan
from forge_agent.web.routes._helpers import Ctx, project_url, resolve_llm_chat

router = APIRouter()


class ArchitectPlanPayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    keyword: str | None = None
    use_llm: bool = False


@router.post("/architect/plan")
async def architect_plan(payload: ArchitectPlanPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        llm_chat = resolve_llm_chat(ctx.tenant, ctx.project_root) if payload.use_llm else None
        return await generate_plan(
            payload.requirement,
            keyword=payload.keyword,
            use_llm=payload.use_llm,
            llm_chat=llm_chat,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ArchitectApplyPayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    keyword: str | None = None
    use_llm: bool = False
    overwrite: bool = False
    pipeline_id: str | None = None
    plan: dict[str, Any] | None = None


@router.post("/architect/apply")
async def architect_apply(payload: ArchitectApplyPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        if payload.plan is not None:
            plan = payload.plan
        else:
            llm_chat = resolve_llm_chat(ctx.tenant, ctx.project_root) if payload.use_llm else None
            plan = await generate_plan(
                payload.requirement,
                keyword=payload.keyword,
                use_llm=payload.use_llm,
                llm_chat=llm_chat,
            )
        result = apply_plan(
            ctx.project_root,
            plan,
            pipeline_id=payload.pipeline_id,
            overwrite=payload.overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pid = result["pipeline_id"]
    return {
        **result,
        "run_url": project_url(ctx.tenant_id, ctx.project_id, f"/pipelines/{pid}/run"),
        "workspace_url": project_url(ctx.tenant_id, ctx.project_id, "/"),
    }
