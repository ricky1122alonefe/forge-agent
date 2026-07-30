"""Agent type management routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge_agent.builtin.tenant_types import (
    delete_tenant_agent_type,
    load_tenant_agent_type,
    save_tenant_agent_type,
)
from forge_agent.web.routes._helpers import Ctx, registry_for

router = APIRouter()


@router.get("/agent-types")
async def get_agent_types(ctx: Ctx) -> dict[str, Any]:
    return {"types": registry_for(ctx).list_with_source()}


class SaveTenantAgentTypePayload(BaseModel):
    agent_type: dict[str, Any]


@router.post("/agent-types")
async def save_tenant_agent_type_api(
    payload: SaveTenantAgentTypePayload, ctx: Ctx
) -> dict[str, Any]:
    try:
        path = save_tenant_agent_type(ctx.tenant, payload.agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    type_id = str(payload.agent_type["type_id"])
    return {
        "success": True,
        "type_id": type_id,
        "path": str(path),
        "agent_type": registry_for(ctx).get(type_id),
        "source": "tenant",
    }


@router.delete("/agent-types/{type_id}")
async def delete_tenant_agent_type_api(type_id: str, ctx: Ctx) -> dict[str, Any]:
    if load_tenant_agent_type(ctx.tenant, type_id) is None:
        raise HTTPException(status_code=404, detail=f"Tenant agent type {type_id!r} not found")
    delete_tenant_agent_type(ctx.tenant, type_id)
    return {"success": True, "type_id": type_id}
