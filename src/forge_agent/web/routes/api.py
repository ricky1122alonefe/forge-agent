"""API routes for the self-hosted web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project.agent_builder import build_agent_yaml, build_pipeline_yaml
from forge_agent.project.launcher import _run_pipeline
from forge_agent.web.bundles import (
    build_market_catalog,
    export_agent_bundle,
    export_pipeline_bundle,
    import_bundle,
    load_shared_bundle,
    save_shared_bundle,
)
from forge_agent.web.context import ProjectContext, get_project_context, project_url
from forge_agent.web.data import collect_payload_fields, get_agent_config
from forge_agent.web.llm_settings import (
    get_llm_settings_view,
    load_env_files,
    save_api_key,
    update_llm_config,
)
from forge_agent.web.presets import (
    AGENT_PRESETS,
    PIPELINE_PRESETS,
    get_pipeline_preset,
    get_preset,
)

router = APIRouter(prefix="/api")
Ctx = Annotated[ProjectContext, Depends(get_project_context)]


@router.get("/agent-types")
async def get_agent_types(ctx: Ctx) -> dict[str, Any]:
    """List available agent types."""
    registry = AgentTypeRegistry(tenant_shared_dir=ctx.tenant.get_shared_path())
    return {"types": registry.list()}


class CreateAgentPayload(BaseModel):
    agent_type: str
    agent_id: str
    params: dict[str, Any] = Field(default_factory=dict)


def _agent_path(project_root: Path, agent_id: str) -> Path:
    return project_root / "agents" / f"{agent_id}.yaml"


def _pipeline_path(project_root: Path, pipeline_id: str) -> Path:
    return project_root / "pipelines" / f"{pipeline_id}.yaml"


@router.post("/agents")
async def create_agent(payload: CreateAgentPayload, ctx: Ctx) -> dict[str, Any]:
    """Create a new agent YAML file from a selected agent type."""
    registry = AgentTypeRegistry(tenant_shared_dir=ctx.tenant.get_shared_path())

    try:
        type_def = registry.get(payload.agent_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agents_dir = ctx.project_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    target = _agent_path(ctx.project_root, payload.agent_id)
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Agent {payload.agent_id!r} already exists")

    yaml_text = build_agent_yaml(type_def, payload.agent_id, payload.params)
    target.write_text(yaml_text, encoding="utf-8")
    return {"success": True, "path": str(target), "agent_id": payload.agent_id}


@router.get("/agent-presets")
async def list_agent_presets() -> dict[str, Any]:
    """List one-click agent presets for the web UI."""
    return {"presets": AGENT_PRESETS}


class CreateAgentFromPresetPayload(BaseModel):
    preset_id: str
    agent_id: str | None = None


@router.post("/agents/from-preset")
async def create_agent_from_preset(
    payload: CreateAgentFromPresetPayload, ctx: Ctx
) -> dict[str, Any]:
    """Create an agent from a built-in preset."""
    preset = get_preset(payload.preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Preset {payload.preset_id!r} not found")

    agent_id = payload.agent_id or preset["default_agent_id"]
    create_payload = CreateAgentPayload(
        agent_type=preset["agent_type"],
        agent_id=agent_id,
        params=preset.get("params", {}),
    )
    return await create_agent(create_payload, ctx)


async def _ensure_agent_from_preset(preset_id: str, ctx: Ctx) -> tuple[str, bool]:
    """Create an agent from preset if missing. Returns (agent_id, was_created)."""
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Agent preset {preset_id!r} not found")

    agent_id = preset["default_agent_id"]
    if _agent_path(ctx.project_root, agent_id).exists():
        return agent_id, False

    await create_agent(
        CreateAgentPayload(
            agent_type=preset["agent_type"],
            agent_id=agent_id,
            params=preset.get("params", {}),
        ),
        ctx,
    )
    return agent_id, True


@router.get("/pipeline-presets")
async def list_pipeline_presets() -> dict[str, Any]:
    """List one-click pipeline presets for the web UI."""
    return {"presets": PIPELINE_PRESETS}


class CreatePipelineFromPresetPayload(BaseModel):
    preset_id: str


@router.post("/pipelines/from-preset")
async def create_pipeline_from_preset(
    payload: CreatePipelineFromPresetPayload, ctx: Ctx
) -> dict[str, Any]:
    """Create agents (if needed) and a pipeline from a built-in preset."""
    preset = get_pipeline_preset(payload.preset_id)
    if preset is None:
        raise HTTPException(
            status_code=404, detail=f"Pipeline preset {payload.preset_id!r} not found"
        )

    agents_created: list[str] = []
    agent_ids: list[str] = []
    for agent_preset_id in preset.get("agent_presets", []):
        agent_id, created = await _ensure_agent_from_preset(agent_preset_id, ctx)
        agent_ids.append(agent_id)
        if created:
            agents_created.append(agent_id)

    if not agent_ids:
        raise HTTPException(status_code=400, detail="Pipeline preset has no valid agents")

    pipeline_id = preset["pipeline_id"]
    target = _pipeline_path(ctx.project_root, pipeline_id)
    pipeline_created = False
    if not target.exists():
        pipelines_dir = ctx.project_root / "pipelines"
        pipelines_dir.mkdir(exist_ok=True)
        yaml_text = build_pipeline_yaml(
            pipeline_id,
            preset["pipeline_name"],
            agent_ids,
            chief_id=preset.get("chief_id"),
            mode=preset.get("mode", "parallel"),
            description=preset.get("pipeline_description", preset.get("description", "")),
        )
        target.write_text(yaml_text, encoding="utf-8")
        pipeline_created = True

    run_url = project_url(ctx.tenant_id, ctx.project_id, f"/pipelines/{pipeline_id}/run")
    return {
        "success": True,
        "preset_id": payload.preset_id,
        "pipeline_id": pipeline_id,
        "pipeline_name": preset["pipeline_name"],
        "agent_ids": agent_ids,
        "agents_created": agents_created,
        "pipeline_created": pipeline_created,
        "run_url": run_url,
        "workspace_url": project_url(ctx.tenant_id, ctx.project_id, "/"),
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Return the raw YAML content of an agent."""
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return {"agent_id": agent_id, "yaml": target.read_text(encoding="utf-8")}


@router.get("/agents/{agent_id}/config")
async def get_agent_config_api(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Return structured config fields for an agent."""
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return get_agent_config(ctx.project_root, agent_id)


class UpdateAgentConfigPayload(BaseModel):
    mock_mode: bool | None = None
    prompt: str | None = None
    tools: list[str] | None = None


def _merge_agent_config_yaml(
    agent_id: str, yaml_text: str, updates: UpdateAgentConfigPayload
) -> str:
    data = yaml.safe_load(yaml_text) or {}
    agents = data.get("agents", []) if isinstance(data, dict) else data
    if not isinstance(agents, list):
        raise ValueError("Agent YAML must contain an 'agents' list")

    target_agent: dict[str, Any] | None = None
    for agent in agents:
        if isinstance(agent, dict) and agent.get("agent_id") == agent_id:
            target_agent = agent
            break
    if target_agent is None:
        raise ValueError(f"Agent {agent_id!r} not found in YAML")

    config = target_agent.setdefault("config", {})
    if not isinstance(config, dict):
        raise ValueError("Agent config must be a mapping")

    if updates.mock_mode is not None:
        config["mock_mode"] = updates.mock_mode
    if updates.prompt is not None:
        config["prompt"] = updates.prompt
    if updates.tools is not None:
        config["tools"] = updates.tools

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


@router.put("/agents/{agent_id}/config")
async def update_agent_config(
    agent_id: str, payload: UpdateAgentConfigPayload, ctx: Ctx
) -> dict[str, Any]:
    """Update selected agent config fields without hand-editing YAML."""
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")

    try:
        merged = _merge_agent_config_yaml(agent_id, target.read_text(encoding="utf-8"), payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target.write_text(merged, encoding="utf-8")
    return {
        "success": True,
        "agent_id": agent_id,
        "config": get_agent_config(ctx.project_root, agent_id),
    }


@router.get("/pipelines/{pipeline_id}/payload-fields")
async def get_pipeline_payload_fields(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    """Return suggested payload form fields for a pipeline run."""
    if not _pipeline_path(ctx.project_root, pipeline_id).exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    return {"fields": collect_payload_fields(ctx.project_root, pipeline_id)}


class UpdateAgentPayload(BaseModel):
    yaml: str


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, payload: UpdateAgentPayload, ctx: Ctx) -> dict[str, Any]:
    """Overwrite an agent YAML file."""
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    try:
        yaml.safe_load(payload.yaml)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    target.write_text(payload.yaml, encoding="utf-8")
    return {"success": True, "agent_id": agent_id}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, ctx: Ctx) -> Response:
    """Delete an agent YAML file."""
    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    target.unlink()
    return Response(status_code=204)


class CreatePipelinePayload(BaseModel):
    pipeline_id: str
    name: str
    agent_ids: list[str]
    chief_id: str | None = None
    mode: str = "parallel"
    description: str = ""


@router.post("/pipelines")
async def create_pipeline(payload: CreatePipelinePayload, ctx: Ctx) -> dict[str, Any]:
    """Create a new pipeline YAML file."""
    if not payload.agent_ids:
        raise HTTPException(status_code=400, detail="At least one agent must be selected")

    pipelines_dir = ctx.project_root / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)
    target = _pipeline_path(ctx.project_root, payload.pipeline_id)
    if target.exists():
        raise HTTPException(
            status_code=409, detail=f"Pipeline {payload.pipeline_id!r} already exists"
        )

    yaml_text = build_pipeline_yaml(
        payload.pipeline_id,
        payload.name,
        payload.agent_ids,
        chief_id=payload.chief_id,
        mode=payload.mode,
        description=payload.description,
    )
    target.write_text(yaml_text, encoding="utf-8")
    return {"success": True, "path": str(target), "pipeline_id": payload.pipeline_id}


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    """Return the raw YAML content of a pipeline."""
    target = _pipeline_path(ctx.project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    return {"pipeline_id": pipeline_id, "yaml": target.read_text(encoding="utf-8")}


class UpdatePipelinePayload(BaseModel):
    yaml: str


@router.put("/pipelines/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str, payload: UpdatePipelinePayload, ctx: Ctx
) -> dict[str, Any]:
    """Overwrite a pipeline YAML file."""
    target = _pipeline_path(ctx.project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    try:
        yaml.safe_load(payload.yaml)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    target.write_text(payload.yaml, encoding="utf-8")
    return {"success": True, "pipeline_id": pipeline_id}


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, ctx: Ctx) -> Response:
    """Delete a pipeline YAML file."""
    target = _pipeline_path(ctx.project_root, pipeline_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    target.unlink()
    return Response(status_code=204)


class RunPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, payload: RunPayload, ctx: Ctx) -> dict[str, Any]:
    """Run a pipeline and return the resulting run record."""
    pipeline_path = _pipeline_path(ctx.project_root, pipeline_id)
    if not pipeline_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")

    try:
        record = await _run_pipeline(
            ctx.project_root,
            ctx.tenant_id,
            pipeline_id,
            payload.payload,
            tenant=ctx.tenant,
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {"success": True, "run_id": record.run_id, "record": record.to_dict()}


@router.get("/llm/config")
async def get_llm_config(ctx: Ctx) -> dict[str, Any]:
    """Return effective LLM settings for the current project."""
    load_env_files(ctx.tenant, ctx.project_root)
    return get_llm_settings_view(ctx.tenant, ctx.project_id)


class UpdateLLMConfigPayload(BaseModel):
    primary_id: str | None = None
    providers: dict[str, dict[str, Any]] | None = None


@router.put("/llm/config")
async def put_llm_config(payload: UpdateLLMConfigPayload, ctx: Ctx) -> dict[str, Any]:
    """Update project-level LLM provider settings."""
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
    """Save an API key to the project .env file."""
    load_env_files(ctx.tenant, ctx.project_root)
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
        path = save_api_key(ctx.tenant, ctx.project_root, env_name, payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "env_name": env_name,
        "path": str(path),
        "settings": get_llm_settings_view(ctx.tenant, ctx.project_id),
    }


class TestLLMPayload(BaseModel):
    provider_id: str
    message: str = "Hello, reply with one short sentence."


@router.post("/llm/test")
async def test_llm_provider(payload: TestLLMPayload, ctx: Ctx) -> dict[str, Any]:
    """Test connectivity for a provider (may consume API quota)."""
    from forge_agent.llm import chat
    from forge_agent.llm.registry import get_registry
    from forge_agent.platform import LLMConfigManager

    load_env_files(ctx.tenant, ctx.project_root)
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


def _shared_market_dir(ctx: Ctx) -> Path:
    return ctx.tenant.get_shared_path() / "market"


@router.get("/market/catalog")
async def market_catalog(ctx: Ctx) -> dict[str, Any]:
    """List built-in presets, shared bundles, and project export sources."""
    return build_market_catalog(ctx.project_root, _shared_market_dir(ctx))


@router.get("/agents/{agent_id}/export")
async def export_agent(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Export an agent as a portable bundle."""
    try:
        return export_agent_bundle(ctx.project_root, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pipelines/{pipeline_id}/export")
async def export_pipeline(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    """Export a pipeline and its agents as a bundle."""
    try:
        return export_pipeline_bundle(ctx.project_root, pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ImportBundlePayload(BaseModel):
    bundle: dict[str, Any]
    overwrite: bool = False


@router.post("/bundles/import")
async def import_bundle_api(payload: ImportBundlePayload, ctx: Ctx) -> dict[str, Any]:
    """Import agents/pipeline from a bundle."""
    try:
        return import_bundle(ctx.project_root, payload.bundle, overwrite=payload.overwrite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class PublishBundlePayload(BaseModel):
    pipeline_id: str


@router.post("/bundles/publish")
async def publish_pipeline_bundle(payload: PublishBundlePayload, ctx: Ctx) -> dict[str, Any]:
    """Publish a pipeline bundle to tenant shared/market/."""
    try:
        bundle = export_pipeline_bundle(ctx.project_root, payload.pipeline_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = save_shared_bundle(_shared_market_dir(ctx), bundle)
    return {"success": True, "path": str(path), "filename": path.name}


class ImportSharedPayload(BaseModel):
    filename: str
    overwrite: bool = False


@router.post("/bundles/import-shared")
async def import_shared_bundle(payload: ImportSharedPayload, ctx: Ctx) -> dict[str, Any]:
    """Import a bundle from tenant shared/market/."""
    try:
        bundle = load_shared_bundle(_shared_market_dir(ctx), payload.filename)
        result = import_bundle(ctx.project_root, bundle, overwrite=payload.overwrite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "filename": payload.filename}
