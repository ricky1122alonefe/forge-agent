"""Natural-language pipeline architect — backed by AgentSpecGenerator (A3.4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from forge_agent.agent_spec.generator import (
    detect_primitive,
    extract_keyword,
    generate_spec_rule_based,
)
from forge_agent.agent_spec.models import AgentPrimitive
from forge_agent.agent_spec.tool_match import match_platforms
from forge_agent.agent_spec.writer import spec_to_agent_dict


def _slug_pipeline_id(requirement: str, keyword: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", keyword.lower())[:20].strip("_") or "trend"
    return f"nl_{base}"


def _specs_for_pipeline(requirement: str, *, keyword: str | None = None) -> list[Any]:
    """Build one or more AgentSpecs for a pipeline requirement."""
    from forge_agent.agent_spec.models import AgentSpec

    kw = extract_keyword(requirement, keyword)
    primitive = detect_primitive(requirement)
    platforms = match_platforms(requirement)
    specs: list[AgentSpec] = []

    if primitive == AgentPrimitive.FETCHER and len(platforms) > 1:
        for pm in platforms:
            spec = generate_spec_rule_based(
                f"分析 {kw} 在{pm.label}的热度",
                agent_id=f"{pm.platform}_analyst",
                keyword=kw,
            )
            spec.config["tools"] = [pm.tool_name]
            spec.config["platform"] = pm.platform
            spec.tags = ["architect", pm.platform, "generated"]
            specs.append(spec)
        return specs

    if primitive == AgentPrimitive.FETCHER and platforms:
        pm = platforms[0]
        spec = generate_spec_rule_based(
            requirement,
            agent_id=f"{pm.platform}_analyst",
            keyword=kw,
        )
        spec.config["tools"] = [pm.tool_name]
        spec.config["platform"] = pm.platform
        spec.tags = ["architect", pm.platform, "generated"]
        return [spec]

    spec = generate_spec_rule_based(requirement, keyword=kw)
    spec.tags = ["architect", "generated"]
    return [spec]


def generate_plan_rule_based(requirement: str, *, keyword: str | None = None) -> dict[str, Any]:
    """Build a mock-friendly pipeline plan using AgentSpecGenerator."""
    kw = extract_keyword(requirement, keyword)
    specs = _specs_for_pipeline(requirement, keyword=keyword)
    agents = [spec_to_agent_dict(s) for s in specs]
    return _normalize_plan(
        {
            "requirement": requirement,
            "keyword": kw,
            "pipeline_id": _slug_pipeline_id(requirement, kw),
            "pipeline_name": f"{kw} 分析 Pipeline",
            "planner": "agent_spec",
            "agents": agents,
            "team": {"mode": "parallel", "chief_id": "generic.chief"},
            "new_tools": [],
        }
    )


async def generate_plan_with_llm(
    requirement: str,
    *,
    keyword: str | None = None,
    llm_chat: Any = None,
) -> dict[str, Any]:
    from forge_agent.agent_spec.generator import generate_spec

    plan = generate_plan_rule_based(requirement, keyword=keyword)
    if llm_chat is not None:
        spec = await generate_spec(requirement, keyword=keyword, use_llm=True, llm_chat=llm_chat)
        plan["planner"] = spec.planner
        if len(plan["agents"]) == 1:
            plan["agents"] = [spec_to_agent_dict(spec)]
    else:
        plan["planner"] = "rule_fallback"
    return plan


async def generate_plan(
    requirement: str,
    *,
    keyword: str | None = None,
    use_llm: bool = False,
    llm_chat: Any = None,
) -> dict[str, Any]:
    requirement = requirement.strip()
    if not requirement:
        raise ValueError("requirement is required")
    if use_llm:
        try:
            return await generate_plan_with_llm(requirement, keyword=keyword, llm_chat=llm_chat)
        except Exception:
            plan = generate_plan_rule_based(requirement, keyword=keyword)
            plan["planner"] = "rule_fallback"
            return plan
    return generate_plan_rule_based(requirement, keyword=keyword)


def _normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    keyword = plan.get("keyword", "demo")
    agents: list[dict[str, Any]] = []
    for idx, agent in enumerate(plan.get("agents", [])):
        agent_id = str(agent.get("agent_id", f"agent_{idx}"))
        config = dict(agent.get("config", {}))
        config.setdefault("mock_mode", True)
        tools = config.get("tools") or []
        if isinstance(tools, str):
            config["tools"] = [tools]
        entry = {
            "agent_id": agent_id,
            "name": agent.get("name", agent_id),
            "domain": agent.get("domain", "generic"),
            "template": agent.get("template", "prompt_agent"),
            "tags": agent.get("tags", ["architect"]),
            "config": config,
        }
        if agent.get("mock_cases"):
            entry["mock_cases"] = agent["mock_cases"]
        if agent.get("_meta"):
            entry["_meta"] = agent["_meta"]
        agents.append(entry)

    team = dict(plan.get("team", {}))
    team.setdefault("mode", "parallel")
    team.setdefault("chief_id", "generic.chief")

    return {
        "requirement": plan.get("requirement", ""),
        "keyword": keyword,
        "pipeline_id": plan.get("pipeline_id")
        or _slug_pipeline_id(plan.get("requirement", ""), keyword),
        "pipeline_name": plan.get("pipeline_name", f"{keyword} 分析 Pipeline"),
        "planner": plan.get("planner", "agent_spec"),
        "agents": agents,
        "team": team,
        "new_tools": plan.get("new_tools", []),
        "agent_ids": [a["agent_id"] for a in agents],
    }


def apply_plan(
    project_root: Path,
    plan: dict[str, Any],
    *,
    pipeline_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write architect plan agents + pipeline YAML into a project."""
    normalized = _normalize_plan(plan)
    pid = pipeline_id or normalized["pipeline_id"]
    agents_dir = project_root / "agents"
    pipelines_dir = project_root / "pipelines"
    agents_dir.mkdir(parents=True, exist_ok=True)
    pipelines_dir.mkdir(parents=True, exist_ok=True)

    created_agents: list[str] = []
    skipped_agents: list[str] = []
    for agent in normalized["agents"]:
        aid = agent["agent_id"]
        path = agents_dir / f"{aid}.yaml"
        if path.exists() and not overwrite:
            skipped_agents.append(aid)
            continue
        path.write_text(
            yaml.safe_dump({"agents": [agent]}, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        created_agents.append(aid)

    pipeline_path = pipelines_dir / f"{pid}.yaml"
    if pipeline_path.exists() and not overwrite:
        raise ValueError(f"Pipeline {pid!r} already exists")

    agent_ids = normalized["agent_ids"]
    if skipped_agents:
        agent_ids = list(dict.fromkeys([*agent_ids, *skipped_agents]))

    pipeline_doc = {
        "pipeline_id": pid,
        "name": normalized["pipeline_name"],
        "description": normalized.get("requirement", ""),
        "team": {
            "team_id": f"{pid}_team",
            "name": f"{normalized['pipeline_name']} Team",
            "domain": "generic",
            "agent_ids": agent_ids,
            "chief_id": normalized["team"].get("chief_id", "generic.chief"),
            "mode": normalized["team"].get("mode", "parallel"),
        },
    }
    pipeline_path.write_text(
        yaml.safe_dump(pipeline_doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    return {
        "success": True,
        "pipeline_id": pid,
        "keyword": normalized["keyword"],
        "planner": normalized["planner"],
        "agents_created": created_agents,
        "agents_skipped": skipped_agents,
        "agent_ids": agent_ids,
        "new_tools": normalized.get("new_tools", []),
    }
