"""Bundle import/export and market routes (S4.1 split)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge_agent.web.bundles import (
    build_market_catalog,
    export_agent_bundle,
    export_pipeline_bundle,
    import_bundle,
    load_shared_bundle,
    save_shared_bundle,
)
from forge_agent.web.routes._helpers import Ctx, _shared_market_dir

router = APIRouter()


@router.get("/market/catalog")
async def market_catalog(ctx: Ctx) -> dict[str, Any]:
    return build_market_catalog(ctx.project_root, _shared_market_dir(ctx))


@router.get("/agents/{agent_id}/export")
async def export_agent(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    try:
        return export_agent_bundle(ctx.project_root, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pipelines/{pipeline_id}/export")
async def export_pipeline(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    try:
        return export_pipeline_bundle(ctx.project_root, pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ImportBundlePayload(BaseModel):
    bundle: dict[str, Any] | None = None
    bundle_text: str | None = None
    overwrite: bool = False
    migrate: bool = True
    run_ci: bool = False


@router.post("/bundles/import")
async def import_bundle_api(payload: ImportBundlePayload, ctx: Ctx) -> dict[str, Any]:
    try:
        if payload.bundle is not None:
            data = payload.bundle
        elif payload.bundle_text:
            from forge_agent.web.bundles import parse_bundle_text

            data = parse_bundle_text(payload.bundle_text)
        else:
            raise ValueError("bundle or bundle_text is required")
        return import_bundle(
            ctx.project_root,
            data,
            overwrite=payload.overwrite,
            migrate=payload.migrate,
            ci_gate=payload.run_ci,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class PublishBundlePayload(BaseModel):
    pipeline_id: str


@router.post("/bundles/publish")
async def publish_pipeline_bundle(payload: PublishBundlePayload, ctx: Ctx) -> dict[str, Any]:
    try:
        bundle = export_pipeline_bundle(ctx.project_root, payload.pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = save_shared_bundle(_shared_market_dir(ctx), bundle)
    return {"success": True, "path": str(path), "filename": path.name}


class ImportSharedPayload(BaseModel):
    filename: str
    overwrite: bool = False
    migrate: bool = True
    run_ci: bool = False


@router.post("/bundles/import-shared")
async def import_shared_bundle(payload: ImportSharedPayload, ctx: Ctx) -> dict[str, Any]:
    try:
        bundle = load_shared_bundle(_shared_market_dir(ctx), payload.filename)
        result = import_bundle(
            ctx.project_root,
            bundle,
            overwrite=payload.overwrite,
            migrate=payload.migrate,
            ci_gate=payload.run_ci,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "filename": payload.filename}
