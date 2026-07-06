"""Compose multiple AgentSpecs + pipeline wiring from one requirement (A9.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge_agent.agent_spec.capabilities import apply_requirement_capabilities
from forge_agent.agent_spec.generator import (
    SYNTHESIZER_KEYWORDS,
    _build_fetcher_spec,
    _build_searcher_spec,
    _build_synthesizer_spec,
    _contains_any,
    _guess_name,
    _slug_agent_id,
    detect_primitive,
    extract_keyword,
    generate_spec_rule_based,
)
from forge_agent.agent_spec.models import AgentPrimitive, AgentSpec
from forge_agent.agent_spec.tool_match import PlatformMatch, match_platforms
from forge_agent.agent_spec.wire import suggest_team_mode, validate_wiring
from forge_agent.agent_spec.writer import apply_spec
from forge_agent.project.agent_builder import build_pipeline, build_pipeline_yaml


@dataclass
class ComposePlan:
    """Multi-agent composition with auto-wired pipeline suggestion."""

    requirement: str
    specs: list[AgentSpec]
    pipeline_id: str
    pipeline_name: str
    agent_ids: list[str]
    mode: str
    chief_id: str = "generic.chief"
    wiring_errors: list[str] = field(default_factory=list)
    keyword: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "specs": [s.to_dict() for s in self.specs],
            "pipeline": {
                "pipeline_id": self.pipeline_id,
                "name": self.pipeline_name,
                "agent_ids": self.agent_ids,
                "mode": self.mode,
                "chief_id": self.chief_id,
            },
            "wiring_valid": not self.wiring_errors,
            "wiring_errors": self.wiring_errors,
            "keyword": self.keyword,
        }


def _needs_synthesis(requirement: str, platforms: list[PlatformMatch]) -> bool:
    if _contains_any(requirement, SYNTHESIZER_KEYWORDS):
        return True
    if len(platforms) > 1:
        return True
    return bool(re.search(r"汇总|综合|合并|一份报告|一份结论", requirement))


def _fetcher_for_platform(
    requirement: str,
    platform: PlatformMatch,
    keyword: str,
) -> AgentSpec:
    slug = _slug_agent_id(keyword)
    agent_id = f"{slug}_{platform.platform}"
    name = f"{keyword} {platform.label}"
    req = f"{requirement} ({platform.label})"
    spec = _build_fetcher_spec(req, agent_id, name, keyword)
    spec.config["platform"] = platform.platform
    spec.config["tools"] = [platform.tool_name]
    return spec


def compose_from_requirement(
    requirement: str,
    *,
    keyword: str | None = None,
    pipeline_id: str | None = None,
    focus: str | None = None,
) -> ComposePlan:
    """Rule-based decomposition: platforms → fetchers + optional synthesizer."""
    req = requirement.strip()
    if not req:
        raise ValueError("requirement is required")

    kw = extract_keyword(req, keyword)
    platforms = match_platforms(req)
    specs: list[AgentSpec] = []

    if _needs_synthesis(req, platforms) and platforms:
        for platform in platforms:
            specs.append(_fetcher_for_platform(req, platform, kw))
        synth_id = f"{_slug_agent_id(kw)}_synth"
        specs.append(
            _build_synthesizer_spec(
                req,
                synth_id,
                _guess_name(req, AgentPrimitive.SYNTHESIZER),
                focus or "general",
            )
        )
    elif _needs_synthesis(req, platforms):
        fetch_id = f"{_slug_agent_id(kw)}_fetch"
        specs.append(
            _build_fetcher_spec(req, fetch_id, _guess_name(req, AgentPrimitive.FETCHER), kw)
        )
        synth_id = f"{_slug_agent_id(kw)}_synth"
        specs.append(
            _build_synthesizer_spec(
                req,
                synth_id,
                _guess_name(req, AgentPrimitive.SYNTHESIZER),
                focus or "general",
            )
        )
    elif platforms:
        if len(platforms) > 1:
            for platform in platforms:
                specs.append(_fetcher_for_platform(req, platform, kw))
            synth_id = f"{_slug_agent_id(kw)}_synth"
            specs.append(
                _build_synthesizer_spec(
                    req,
                    synth_id,
                    f"{kw} 汇总",
                    focus or "general",
                )
            )
        else:
            agent_id = pipeline_id or f"{_slug_agent_id(kw)}_{platforms[0].platform}"
            specs.append(
                _build_fetcher_spec(
                    req,
                    agent_id,
                    _guess_name(req, AgentPrimitive.FETCHER),
                    kw,
                )
            )
    elif detect_primitive(req) == AgentPrimitive.SEARCHER:
        agent_id = pipeline_id or f"{_slug_agent_id(kw)}_search"
        specs.append(
            _build_searcher_spec(req, agent_id, _guess_name(req, AgentPrimitive.SEARCHER), kw)
        )
    else:
        agent_id = pipeline_id or _slug_agent_id(_guess_name(req, detect_primitive(req)))
        specs.append(generate_spec_rule_based(req, agent_id=agent_id, keyword=kw, focus=focus))

    for spec in specs:
        apply_requirement_capabilities(spec, req)

    primitives = [spec.primitive for spec in specs]
    wiring_errors = validate_wiring(primitives)
    mode = suggest_team_mode(primitives)
    agent_ids = [spec.agent_id for spec in specs]

    pid = pipeline_id or f"{_slug_agent_id(kw)}_pipeline"
    pname = f"{kw} 编队" if len(specs) > 1 else specs[0].name

    return ComposePlan(
        requirement=req,
        specs=specs,
        pipeline_id=pid,
        pipeline_name=pname,
        agent_ids=agent_ids,
        mode=mode,
        wiring_errors=wiring_errors,
        keyword=kw,
    )


def apply_compose_plan(
    project_root: Path,
    plan: ComposePlan,
    *,
    overwrite: bool = False,
    ci_gate: bool = True,
) -> dict[str, Any]:
    """Write all agents and pipeline YAML from a compose plan."""
    if plan.wiring_errors:
        raise ValueError("; ".join(plan.wiring_errors))

    if ci_gate:
        from forge_agent.agent_spec.ci import run_ci_gate

        for spec in plan.specs:
            run_ci_gate(spec)
        if len(plan.specs) > 1:
            import asyncio

            from forge_agent.agent_spec.chain_smoke import smoke_compose_chain

            asyncio.run(smoke_compose_chain(plan))

    agents_dir = project_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    pipelines_dir = project_root / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)

    pipeline_path = pipelines_dir / f"{plan.pipeline_id}.yaml"
    if pipeline_path.exists() and not overwrite:
        raise ValueError(f"Pipeline {plan.pipeline_id!r} already exists")

    applied: list[dict[str, Any]] = []
    for spec in plan.specs:
        agent_path = agents_dir / f"{spec.agent_id}.yaml"
        if agent_path.exists() and not overwrite:
            raise ValueError(f"Agent {spec.agent_id!r} already exists")
        applied.append(apply_spec(project_root, spec, overwrite=overwrite, ci_gate=False))

    pipeline = build_pipeline(
        plan.pipeline_id,
        plan.pipeline_name,
        plan.agent_ids,
        chief_id=plan.chief_id,
        mode=plan.mode,
        description=plan.requirement,
    )
    pipeline_path.write_text(
        build_pipeline_yaml(
            plan.pipeline_id,
            plan.pipeline_name,
            plan.agent_ids,
            chief_id=plan.chief_id,
            mode=plan.mode,
            description=plan.requirement,
        ),
        encoding="utf-8",
    )

    return {
        "success": True,
        "pipeline_id": plan.pipeline_id,
        "pipeline_path": str(pipeline_path),
        "agents": applied,
        "mode": plan.mode,
        "agent_ids": plan.agent_ids,
        "pipeline": pipeline,
        "ci_gate": ci_gate,
    }


def compose_plan_from_bundle(data: dict[str, Any]) -> ComposePlan | None:
    """Build a ComposePlan from an imported pipeline bundle for chain smoke (A11.2)."""
    from forge_agent.agent_spec.versioning import migrate_agent_dict
    from forge_agent.agent_spec.writer import agent_dict_to_spec

    pipeline = data.get("pipeline")
    if not isinstance(pipeline, dict):
        return None
    team = pipeline.get("team") if isinstance(pipeline.get("team"), dict) else {}
    agent_ids = list(team.get("agent_ids", [])) if isinstance(team.get("agent_ids"), list) else []
    if len(agent_ids) < 2:
        return None

    agents_by_id = {
        str(a["agent_id"]): migrate_agent_dict(dict(a))
        for a in data.get("agents", [])
        if isinstance(a, dict) and a.get("agent_id")
    }
    specs: list[AgentSpec] = []
    for agent_id in agent_ids:
        agent = agents_by_id.get(agent_id)
        if agent is None:
            return None
        specs.append(agent_dict_to_spec(agent))

    primitives = [spec.primitive for spec in specs]
    return ComposePlan(
        requirement=str(
            pipeline.get("description") or data.get("description") or "imported bundle"
        ),
        specs=specs,
        pipeline_id=str(pipeline.get("pipeline_id", "imported_pipeline")),
        pipeline_name=str(pipeline.get("name", pipeline.get("pipeline_id", "Imported"))),
        agent_ids=list(agent_ids),
        mode=str(team.get("mode", suggest_team_mode(primitives))),
        wiring_errors=validate_wiring(primitives),
        keyword=str(data.get("keyword") or "demo"),
    )
