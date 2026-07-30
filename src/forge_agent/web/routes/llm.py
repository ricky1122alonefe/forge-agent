"""LLM configuration routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge_agent.web.llm_settings import (
    bootstrap_project_secrets,
    get_llm_settings_view,
    save_api_key,
    update_llm_config,
)
from forge_agent.web.routes._helpers import Ctx

router = APIRouter()


@router.get("/llm/config")
async def get_llm_config(ctx: Ctx) -> dict[str, Any]:
    bootstrap_project_secrets(ctx.tenant, ctx.project_root)
    return get_llm_settings_view(ctx.tenant, ctx.project_id)


class UpdateLLMConfigPayload(BaseModel):
    primary_id: str | None = None
    providers: dict[str, dict[str, Any]] | None = None


@router.put("/llm/config")
async def put_llm_config(payload: UpdateLLMConfigPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        return update_llm_config(
            ctx.tenant,
            ctx.project_id,
            primary_id=payload.primary_id,
            provider_updates=payload.providers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class SaveLLMSecretPayload(BaseModel):
    provider_id: str
    api_key: str


@router.put("/llm/secrets")
async def put_llm_secret(payload: SaveLLMSecretPayload, ctx: Ctx) -> dict[str, Any]:
    cfg_view = get_llm_settings_view(ctx.tenant, ctx.project_id)
    provider = next(
        (p for p in cfg_view["providers"] if p["provider_id"] == payload.provider_id),
        None,
    )
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider {payload.provider_id!r} not found")
    env_name = provider.get("api_key_env")
    if not env_name:
        raise HTTPException(status_code=400, detail="Provider does not use an API key")

    try:
        saved = save_api_key(ctx.tenant, ctx.project_root, env_name, payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "env_name": env_name,
        "storage": saved["storage"],
        "db_path": saved["db_path"],
        "settings": get_llm_settings_view(ctx.tenant, ctx.project_id),
    }


class TestLLMPayload(BaseModel):
    provider_id: str
    message: str = "Hello, reply with one short sentence."


@router.post("/llm/test")
async def test_llm_provider(payload: TestLLMPayload, ctx: Ctx) -> dict[str, Any]:
    from forge_agent.llm import chat
    from forge_agent.llm.registry import get_registry
    from forge_agent.platform import LLMConfigManager

    bootstrap_project_secrets(ctx.tenant, ctx.project_root)
    cfg = LLMConfigManager(ctx.tenant).load(ctx.project_id)
    get_registry().configure(cfg)

    try:
        response = await chat(payload.message, provider=payload.provider_id)
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "provider_id": payload.provider_id,
        "model": response.model,
        "latency_ms": response.latency_ms,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "content_preview": response.content[:200],
    }
