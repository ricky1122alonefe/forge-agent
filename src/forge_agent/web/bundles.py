"""Agent/Pipeline bundle export and import (Phase 4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from forge_agent.web.data import get_agent, list_agents, list_pipelines
from forge_agent.web.presets import AGENT_PRESETS, PIPELINE_PRESETS

BUNDLE_KIND = "forge_agent_bundle"
BUNDLE_VERSION = 1


def _agent_yaml_text(agent: dict[str, Any]) -> str:
    return yaml.safe_dump({"agents": [agent]}, sort_keys=False, allow_unicode=True)


def export_agent_bundle(project_root: Path, agent_id: str) -> dict[str, Any]:
    """Export a single agent as a portable bundle."""
    agent = get_agent(project_root, agent_id)
    if agent is None:
        raise ValueError(f"Agent {agent_id!r} not found")
    meta = agent.get("_meta") if isinstance(agent.get("_meta"), dict) else {}
    return {
        "kind": BUNDLE_KIND,
        "version": BUNDLE_VERSION,
        "bundle_id": f"agent:{agent_id}",
        "name": agent.get("name") or agent_id,
        "description": f"Agent export: {agent_id}",
        "agents": [agent],
        "pipeline": None,
        "mock_cases_count": len(agent.get("mock_cases") or []),
        "agent_spec_version": meta.get("spec_version"),
        "agent_revision": meta.get("revision"),
        "generated_at": meta.get("generated_at"),
    }


def export_pipeline_bundle(project_root: Path, pipeline_id: str) -> dict[str, Any]:
    """Export a pipeline and its referenced agents as a bundle."""
    pipeline_path = project_root / "pipelines" / f"{pipeline_id}.yaml"
    if not pipeline_path.is_file():
        raise ValueError(f"Pipeline {pipeline_id!r} not found")

    pipeline = yaml.safe_load(pipeline_path.read_text(encoding="utf-8")) or {}
    team = pipeline.get("team", {}) if isinstance(pipeline, dict) else {}
    agent_ids = list(team.get("agent_ids", [])) if isinstance(team, dict) else []

    agents: list[dict[str, Any]] = []
    missing: list[str] = []
    for aid in agent_ids:
        agent = get_agent(project_root, aid)
        if agent is None:
            missing.append(aid)
            continue
        agents.append(agent)

    bundle = {
        "kind": BUNDLE_KIND,
        "version": BUNDLE_VERSION,
        "bundle_id": f"pipeline:{pipeline_id}",
        "name": pipeline.get("name", pipeline_id),
        "description": pipeline.get("description", ""),
        "agents": agents,
        "pipeline": pipeline,
    }
    if missing:
        bundle["warnings"] = [f"missing agents not exported: {', '.join(missing)}"]
    return bundle


def export_compose_bundle(plan: Any) -> dict[str, Any]:
    """Export a compose plan as a portable pipeline bundle (A12.1)."""
    from forge_agent.agent_spec.versioning import stamp_agent_meta
    from forge_agent.agent_spec.writer import spec_to_agent_dict
    from forge_agent.project.agent_builder import build_pipeline

    agents: list[dict[str, Any]] = []
    for spec in plan.specs:
        agent_dict = spec_to_agent_dict(spec)
        agent_dict["_meta"] = stamp_agent_meta(agent_dict["_meta"], revision=1)
        agents.append(agent_dict)

    pipeline = build_pipeline(
        plan.pipeline_id,
        plan.pipeline_name,
        plan.agent_ids,
        chief_id=plan.chief_id,
        mode=plan.mode,
        description=plan.requirement,
    )

    return {
        "kind": BUNDLE_KIND,
        "version": BUNDLE_VERSION,
        "bundle_id": f"pipeline:{plan.pipeline_id}",
        "name": plan.pipeline_name,
        "description": plan.requirement,
        "agents": agents,
        "pipeline": pipeline,
        "keyword": plan.keyword,
        "composed": True,
        "wiring_valid": not plan.wiring_errors,
        "agent_count": len(agents),
    }


def validate_bundle(data: dict[str, Any]) -> None:
    if data.get("kind") != BUNDLE_KIND:
        raise ValueError(f"Unsupported bundle kind: {data.get('kind')!r}")
    if data.get("version") != BUNDLE_VERSION:
        raise ValueError(f"Unsupported bundle version: {data.get('version')!r}")
    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        raise ValueError("Bundle must include at least one agent")
    for agent in agents:
        if not isinstance(agent, dict) or not agent.get("agent_id"):
            raise ValueError("Each agent entry must include agent_id")


def parse_bundle_text(text: str) -> dict[str, Any]:
    """Parse a bundle from JSON or YAML text."""
    raw = text.strip()
    if not raw:
        raise ValueError("Bundle text is empty")
    try:
        data = json.loads(raw) if raw.startswith("{") else yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid bundle format: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Bundle must be a JSON/YAML object")
    validate_bundle(data)
    return data


def import_bundle(
    project_root: Path,
    data: dict[str, Any],
    *,
    overwrite: bool = False,
    migrate: bool = True,
    ci_gate: bool = False,
) -> dict[str, Any]:
    """Import agents and optional pipeline from a bundle."""
    validate_bundle(data)

    ci_skipped: list[str] = []
    chain_result: dict[str, Any] | None = None

    if ci_gate:
        from forge_agent.agent_spec.ci import run_ci_gate
        from forge_agent.agent_spec.compose import compose_plan_from_bundle
        from forge_agent.agent_spec.versioning import migrate_agent_dict
        from forge_agent.agent_spec.writer import agent_dict_to_spec

        prepared_agents: list[dict[str, Any]] = []
        for raw in data["agents"]:
            agent = migrate_agent_dict(dict(raw)) if migrate else dict(raw)
            agent_id = str(agent["agent_id"])
            mock_cases = agent.get("mock_cases")
            if isinstance(mock_cases, list) and mock_cases:
                run_ci_gate(agent_dict_to_spec(agent))
            else:
                ci_skipped.append(agent_id)
            prepared_agents.append(agent)

        plan = compose_plan_from_bundle({**data, "agents": prepared_agents})
        if plan is not None:
            if plan.wiring_errors:
                raise ValueError("; ".join(plan.wiring_errors))
            from forge_agent.agent_spec.chain_smoke import smoke_compose_chain
            from forge_agent.utils.async_utils import run_sync

            chain_result = run_sync(smoke_compose_chain(plan))

        data = {**data, "agents": prepared_agents}
    elif migrate:
        from forge_agent.agent_spec.versioning import migrate_agent_dict

        data = {**data, "agents": [migrate_agent_dict(dict(a)) for a in data["agents"]]}

    agents_dir = project_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    pipelines_dir = project_root / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)

    created_agents: list[str] = []
    skipped_agents: list[str] = []
    for agent in data["agents"]:
        agent_id = str(agent["agent_id"])
        target = agents_dir / f"{agent_id}.yaml"
        if target.exists() and not overwrite:
            skipped_agents.append(agent_id)
            continue
        target.write_text(_agent_yaml_text(agent), encoding="utf-8")
        created_agents.append(agent_id)

    pipeline_result: dict[str, Any] | None = None
    pipeline = data.get("pipeline")
    if isinstance(pipeline, dict) and pipeline.get("pipeline_id"):
        pipeline_id = str(pipeline["pipeline_id"])
        target = pipelines_dir / f"{pipeline_id}.yaml"
        if target.exists() and not overwrite:
            pipeline_result = {"pipeline_id": pipeline_id, "created": False, "skipped": True}
        else:
            target.write_text(
                yaml.safe_dump(pipeline, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            pipeline_result = {"pipeline_id": pipeline_id, "created": True, "skipped": False}

    return {
        "success": True,
        "agents_created": created_agents,
        "agents_skipped": skipped_agents,
        "pipeline": pipeline_result,
        "migrated": migrate,
        "ci_gate": ci_gate,
        "ci_skipped": ci_skipped if ci_gate else [],
        "chain_smoke": chain_result if ci_gate else None,
    }


def list_shared_bundles(shared_market_dir: Path) -> list[dict[str, Any]]:
    """List bundle manifests saved under tenant shared/market/."""
    if not shared_market_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(shared_market_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if data.get("kind") != BUNDLE_KIND:
            continue
        items.append(
            {
                "bundle_id": data.get("bundle_id", path.stem),
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "source": "shared",
                "filename": path.name,
                "agent_count": len(data.get("agents", [])),
                "has_pipeline": bool(data.get("pipeline")),
            }
        )
    return items


def save_shared_bundle(shared_market_dir: Path, bundle: dict[str, Any]) -> Path:
    """Publish a bundle to tenant shared/market/."""
    validate_bundle(bundle)
    shared_market_dir.mkdir(parents=True, exist_ok=True)
    bundle_id = str(bundle.get("bundle_id") or bundle.get("name") or "bundle")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in bundle_id)[:64]
    path = shared_market_dir / f"{safe_name}.yaml"
    path.write_text(yaml.safe_dump(bundle, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_shared_bundle(shared_market_dir: Path, filename: str) -> dict[str, Any]:
    path = shared_market_dir / filename
    if not path.is_file() or ".." in filename:
        raise ValueError(f"Shared bundle {filename!r} not found")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_bundle(data)
    return data


def build_market_catalog(
    project_root: Path,
    shared_market_dir: Path,
) -> dict[str, Any]:
    """Build the template market catalog for the UI."""
    builtin_agents = [
        {
            "preset_id": p["preset_id"],
            "name": p["name"],
            "description": p.get("description", ""),
            "source": "builtin",
            "kind": "agent_preset",
        }
        for p in AGENT_PRESETS
    ]
    builtin_pipelines = [
        {
            "preset_id": p["preset_id"],
            "name": p["name"],
            "description": p.get("description", ""),
            "source": "builtin",
            "kind": "pipeline_preset",
        }
        for p in PIPELINE_PRESETS
    ]
    return {
        "builtin_agents": builtin_agents,
        "builtin_pipelines": builtin_pipelines,
        "shared_bundles": list_shared_bundles(shared_market_dir),
        "project_agents": list_agents(project_root),
        "project_pipelines": list_pipelines(project_root),
    }
