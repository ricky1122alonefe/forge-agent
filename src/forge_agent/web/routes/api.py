"""API routes for the self-hosted web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from forge_agent.agent_spec import (
    AgentSpec,
    agent_dict_to_spec,
    apply_spec,
    generate_spec,
    list_tool_catalog,
    mark_smoke_verified,
    smoke_run_spec,
)
from forge_agent.agent_spec.compose import apply_compose_plan, compose_from_requirement
from forge_agent.agent_spec.coverage import compute_scenario_coverage
from forge_agent.agent_spec.from_type import generate_from_agent_type
from forge_agent.agent_spec.versioning import validate_agent_asset
from forge_agent.builtin.tenant_types import (
    delete_tenant_agent_type,
    load_tenant_agent_type,
    save_tenant_agent_type,
)
from forge_agent.project.agent_builder import build_pipeline_yaml
from forge_agent.project.agent_runner import default_run_payload, run_single_agent
from forge_agent.project.launcher import _run_pipeline
from forge_agent.web.agent_types import registry_for
from forge_agent.web.architect import apply_plan, generate_plan
from forge_agent.web.bundles import (
    build_market_catalog,
    export_agent_bundle,
    export_compose_bundle,
    export_pipeline_bundle,
    import_bundle,
    load_shared_bundle,
    save_shared_bundle,
)
from forge_agent.web.context import ProjectContext, get_project_context, project_url
from forge_agent.web.data import collect_payload_fields, get_agent_config
from forge_agent.web.data import get_agent as load_agent_dict
from forge_agent.web.llm_runtime import resolve_llm_chat
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
    """List available agent types (built-in + tenant)."""
    return {"types": registry_for(ctx).list_with_source()}


class SaveTenantAgentTypePayload(BaseModel):
    agent_type: dict[str, Any]


@router.post("/agent-types")
async def save_tenant_agent_type_api(
    payload: SaveTenantAgentTypePayload, ctx: Ctx
) -> dict[str, Any]:
    """Create or update a tenant-scoped agent type (A5.2)."""
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
    """Delete a tenant agent type definition (built-in types cannot be deleted)."""
    if load_tenant_agent_type(ctx.tenant, type_id) is None:
        raise HTTPException(status_code=404, detail=f"Tenant agent type {type_id!r} not found")
    delete_tenant_agent_type(ctx.tenant, type_id)
    return {"success": True, "type_id": type_id}


class CreateAgentPayload(BaseModel):
    agent_type: str
    agent_id: str
    params: dict[str, Any] = Field(default_factory=dict)


def _agent_path(project_root: Path, agent_id: str) -> Path:
    return project_root / "agents" / f"{agent_id}.yaml"


def _pipeline_path(project_root: Path, pipeline_id: str) -> Path:
    return project_root / "pipelines" / f"{pipeline_id}.yaml"


async def _apply_agent_spec(
    ctx: Ctx,
    spec: AgentSpec,
    *,
    overwrite: bool = False,
    run_smoke: bool = True,
    ci_gate: bool | None = None,
) -> dict[str, Any]:
    """Apply AgentSpec with optional CI gate (smoke before write)."""
    from forge_agent.agent_spec.ci import CIGateError

    gate = run_smoke if ci_gate is None else ci_gate
    try:
        result = apply_spec(ctx.project_root, spec, overwrite=overwrite, ci_gate=gate)
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if gate and spec.mock_cases and result.get("success"):
        mark_smoke_verified(ctx.project_root, spec.agent_id)
        result["smoke_verified"] = True
        if result.get("smoke_results"):
            result["smoke"] = result["smoke_results"][0]
    return result


async def _create_agent_from_type(
    ctx: Ctx,
    agent_type: str,
    agent_id: str,
    params: dict[str, Any],
    *,
    requirement: str = "",
    overwrite: bool = False,
    run_smoke: bool = True,
) -> dict[str, Any]:
    try:
        type_def = registry_for(ctx).get(agent_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = _agent_path(ctx.project_root, agent_id)
    if target.exists() and not overwrite:
        raise HTTPException(status_code=409, detail=f"Agent {agent_id!r} already exists")

    spec = generate_from_agent_type(
        type_def,
        agent_id,
        params,
        requirement=requirement,
    )
    try:
        result = await _apply_agent_spec(ctx, spec, overwrite=overwrite, run_smoke=run_smoke)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **result,
        "agent_id": spec.agent_id,
        "path": str(target),
        "primitive": spec.primitive.value,
        "planner": spec.planner,
        "agent_url": project_url(ctx.tenant_id, ctx.project_id, f"/agents/{spec.agent_id}"),
    }


@router.post("/agents")
async def create_agent(payload: CreateAgentPayload, ctx: Ctx) -> dict[str, Any]:
    """Create a new agent via AgentSpec from a selected agent type (A5.3)."""
    return await _create_agent_from_type(
        ctx,
        payload.agent_type,
        payload.agent_id,
        payload.params,
    )


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


@router.get("/agents/{agent_id}/validate")
async def validate_agent_asset_api(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Validate stored agent YAML meets AgentSpec asset requirements (A8.3)."""
    from forge_agent.agent_spec.versioning import AGENT_ASSET_SPEC_VERSION

    agent = load_agent_dict(ctx.project_root, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    errors = validate_agent_asset(agent)
    meta = agent.get("_meta") if isinstance(agent.get("_meta"), dict) else {}
    return {
        "valid": not errors,
        "errors": errors,
        "spec_version": meta.get("spec_version"),
        "revision": meta.get("revision"),
        "expected_spec_version": AGENT_ASSET_SPEC_VERSION,
    }


@router.post("/agents/{agent_id}/migrate")
async def migrate_agent_asset(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Upgrade legacy agent YAML with spec_version / primitive metadata (A11.1)."""
    import yaml

    from forge_agent.agent_spec.versioning import migrate_agent_dict, validate_agent_asset

    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    agents = raw.get("agents", []) if isinstance(raw, dict) else raw
    migrated = False
    for entry in agents:
        if isinstance(entry, dict) and entry.get("agent_id") == agent_id:
            entry.update(migrate_agent_dict(entry))
            migrated = True
            break
    if not migrated:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found in YAML")
    target.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    agent = load_agent_dict(ctx.project_root, agent_id) or {}
    meta = agent.get("_meta") if isinstance(agent.get("_meta"), dict) else {}
    return {
        "success": True,
        "agent_id": agent_id,
        "spec_version": meta.get("spec_version"),
        "revision": meta.get("revision"),
        "primitive": meta.get("primitive"),
        "validation_errors": validate_agent_asset(agent),
    }


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
    run_ci: bool = True


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
    from forge_agent.agent_spec.ci import CIGateError, persist_agent_document_with_ci

    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")

    try:
        merged_text = _merge_agent_config_yaml(
            agent_id, target.read_text(encoding="utf-8"), payload
        )
        document = yaml.safe_load(merged_text) or {}
        result = persist_agent_document_with_ci(
            ctx.project_root,
            agent_id,
            document,
            ci_gate=payload.run_ci,
        )
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **result,
        "config": get_agent_config(ctx.project_root, agent_id),
    }


@router.post("/agents/{agent_id}/smoke")
async def agent_smoke_test(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Run mock_cases smoke test on an existing agent (A3.2)."""
    from forge_agent.agent_spec.maturity import compute_maturity

    agent = load_agent_dict(ctx.project_root, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    spec = agent_dict_to_spec(agent)
    if not spec.mock_cases:
        raise HTTPException(status_code=400, detail="Agent has no mock_cases defined")
    smoke = await smoke_run_spec(spec)
    if smoke.get("success"):
        mark_smoke_verified(ctx.project_root, agent_id)
    updated = load_agent_dict(ctx.project_root, agent_id) or agent
    return {
        "success": bool(smoke.get("success")),
        "smoke": smoke,
        "maturity": compute_maturity(updated),
    }


class RunAgentPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents/{agent_id}/run")
async def run_agent(agent_id: str, body: RunAgentPayload, ctx: Ctx) -> dict[str, Any]:
    """Run a single Agent with payload — no Pipeline required (A6.1)."""
    try:
        return await run_single_agent(
            ctx.project_root,
            ctx.tenant_id,
            agent_id,
            body.payload,
            tenant=ctx.tenant,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agents/{agent_id}/run-defaults")
async def agent_run_defaults(agent_id: str, ctx: Ctx) -> dict[str, Any]:
    """Return suggested default payload for single-agent run."""
    agent = load_agent_dict(ctx.project_root, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return {"payload": default_run_payload(agent)}


@router.get("/pipelines/{pipeline_id}/payload-fields")
async def get_pipeline_payload_fields(pipeline_id: str, ctx: Ctx) -> dict[str, Any]:
    """Return suggested payload form fields for a pipeline run."""
    if not _pipeline_path(ctx.project_root, pipeline_id).exists():
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id!r} not found")
    return {"fields": collect_payload_fields(ctx.project_root, pipeline_id)}


class UpdateAgentPayload(BaseModel):
    yaml: str
    run_ci: bool = True


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, payload: UpdateAgentPayload, ctx: Ctx) -> dict[str, Any]:
    """Overwrite an agent YAML file."""
    from forge_agent.agent_spec.ci import CIGateError, persist_agent_document_with_ci

    target = _agent_path(ctx.project_root, agent_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    try:
        document = yaml.safe_load(payload.yaml) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc

    try:
        result = persist_agent_document_with_ci(
            ctx.project_root,
            agent_id,
            document,
            ci_gate=payload.run_ci,
        )
    except CIGateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


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
    bundle: dict[str, Any] | None = None
    bundle_text: str | None = None
    overwrite: bool = False
    migrate: bool = True
    run_ci: bool = False


@router.post("/bundles/import")
async def import_bundle_api(payload: ImportBundlePayload, ctx: Ctx) -> dict[str, Any]:
    """Import agents/pipeline from a bundle."""
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
    migrate: bool = True
    run_ci: bool = False


@router.post("/bundles/import-shared")
async def import_shared_bundle(payload: ImportSharedPayload, ctx: Ctx) -> dict[str, Any]:
    """Import a bundle from tenant shared/market/."""
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


class ArchitectPlanPayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    keyword: str | None = None
    use_llm: bool = False


@router.post("/architect/plan")
async def architect_plan(payload: ArchitectPlanPayload, ctx: Ctx) -> dict[str, Any]:
    """Generate a pipeline plan from natural language (P4.4)."""
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
    """Apply an architect plan: write agents + pipeline, return run URL."""
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


class AgentSpecPlanPayload(BaseModel):
    requirement: str = Field(min_length=4, max_length=2000)
    agent_id: str | None = None
    keyword: str | None = None
    focus: str | None = None
    use_llm: bool = False


@router.post("/agent-spec/plan")
async def agent_spec_plan(payload: AgentSpecPlanPayload, ctx: Ctx) -> dict[str, Any]:
    """Generate an AgentSpec preview from natural language (AGENT_PLAN A1.5)."""
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
    """Write a generated AgentSpec to the project agents/ directory."""
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
            ctx,
            spec,
            overwrite=payload.overwrite,
            run_smoke=payload.run_smoke,
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
    """Plan or apply an AgentSpec from a registered agent type (A5.3)."""
    try:
        type_def = registry_for(ctx).get(payload.agent_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = _agent_path(ctx.project_root, payload.agent_id)
    if target.exists() and not payload.overwrite:
        raise HTTPException(status_code=409, detail=f"Agent {payload.agent_id!r} already exists")

    spec = generate_from_agent_type(
        type_def,
        payload.agent_id,
        payload.params,
        requirement=payload.requirement,
    )
    if not payload.apply:
        return {"spec": spec.to_dict(), "applied": False}

    try:
        result = await _apply_agent_spec(
            ctx,
            spec,
            overwrite=payload.overwrite,
            run_smoke=payload.run_smoke,
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
    """List tool metadata for AgentSpec generation (A2.2)."""
    return {"tools": list_tool_catalog()}


@router.get("/agent-spec/coverage")
async def agent_spec_coverage() -> dict[str, Any]:
    """Return 20-scenario routing coverage stats (A4.3)."""
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
    """Decompose a requirement into multiple wired agents + pipeline (A9.2/A9.3)."""
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
            from forge_agent.agent_spec.chain_smoke import smoke_compose_chain
            from forge_agent.agent_spec.ci import CIGateError, run_ci_gate

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

    from forge_agent.agent_spec.ci import CIGateError

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
    """Export a compose plan as a portable bundle JSON (A12.1)."""
    from forge_agent.agent_spec.chain_smoke import smoke_compose_chain
    from forge_agent.agent_spec.ci import CIGateError, run_ci_gate

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
    return {
        "bundle": bundle,
        "plan": plan.to_dict(),
        "chain_smoke": chain_smoke,
    }
