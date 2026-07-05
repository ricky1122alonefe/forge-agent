"""Natural-language pipeline architect for the web UI (P4.4)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from forge_agent.builtin.tools import register_builtin_tools
from forge_agent.platform.tool_registry import get_tool_registry

DEFAULT_PROMPT_TEMPLATE = (
    "你是一位趋势分析专家。请分析以下 {platform} 数据，"
    "判断关键词「{keyword}」相关的热度趋势。\n\n数据：\n{data}\n\n"
    "请输出 JSON，包含 verdict、confidence、risk、evidence、recommended_action、metrics。"
)

DEFAULT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
        "confidence": {"type": "number"},
        "risk": {"type": "number"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "recommended_action": {"type": "string"},
        "metrics": {"type": "object"},
    },
}

DEFAULT_OUTPUT_MAPPING = {
    "verdict": "verdict",
    "confidence": "confidence",
    "risk": "risk",
    "evidence": "evidence",
    "recommended_action": "recommended_action",
    "metrics": "metrics",
}

PLATFORM_RULES: list[tuple[str, str, str, str]] = [
    ("微博", "weibo", "weibo.hot_search", "weibo_analyst"),
    ("小红书", "xiaohongshu", "xiaohongshu.search", "xhs_analyst"),
    ("得物", "dewu", "dewu.search", "dewu_analyst"),
    ("抖音", "douyin", "douyin.hot", "douyin_analyst"),
]


def _mock_response(platform_label: str) -> str:
    return json.dumps(
        {
            "verdict": "lean_positive",
            "confidence": 0.78,
            "risk": 0.18,
            "evidence": [f"{platform_label}: 关键词相关讨论热度上升（Mock 演示）"],
            "recommended_action": "watch",
            "metrics": {},
        },
        ensure_ascii=False,
    )


def extract_keyword(requirement: str, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    quotes = re.findall(r"[「『\"']([^」』\"']+)[」』\"']", requirement)
    if quotes:
        return quotes[0].strip()
    skip = {
        "分析",
        "趋势",
        "热度",
        "潮玩",
        "微博",
        "小红书",
        "得物",
        "抖音",
        "平台",
        "数据",
        "相关",
    }
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", requirement)
    for match in latin:
        if match.lower() not in skip:
            return match
    for match in re.findall(r"[一-龥]{2,12}", requirement):
        if match not in skip:
            return match
    return "labubu"


def _slug_pipeline_id(requirement: str, keyword: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", keyword.lower())[:20].strip("_") or "trend"
    return f"nl_{base}"


def list_available_tools() -> list[str]:
    register_builtin_tools()
    return get_tool_registry().list_names()


def generate_plan_rule_based(requirement: str, *, keyword: str | None = None) -> dict[str, Any]:
    """Build a mock-friendly pipeline plan without calling an LLM."""
    kw = extract_keyword(requirement, keyword)
    tools = set(list_available_tools())
    agents: list[dict[str, Any]] = []

    for label, platform, tool_name, agent_id in PLATFORM_RULES:
        if label in requirement and tool_name in tools:
            agents.append(_agent_entry(label, platform, tool_name, agent_id, kw))

    if not agents:
        agents.append(_agent_entry("微博", "weibo", "weibo.hot_search", "weibo_analyst", kw))

    return _normalize_plan(
        {
            "requirement": requirement,
            "keyword": kw,
            "pipeline_id": _slug_pipeline_id(requirement, kw),
            "pipeline_name": f"{kw} 趋势分析",
            "planner": "rule",
            "agents": agents,
            "team": {
                "mode": "parallel",
                "chief_id": "generic.chief",
            },
            "new_tools": [],
        }
    )


def _agent_entry(
    label: str, platform: str, tool_name: str, agent_id: str, keyword: str
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "name": f"{label}趋势分析",
        "domain": "generic",
        "template": "scraper_agent",
        "tags": ["architect", platform],
        "config": {
            "platform": platform,
            "tools": [tool_name],
            "mock_mode": True,
            "mock_response": _mock_response(label),
            "prompt": DEFAULT_PROMPT_TEMPLATE.format(
                platform=label, keyword="{keyword}", data="{data}"
            ),
            "output_schema": DEFAULT_OUTPUT_SCHEMA,
            "output_mapping": DEFAULT_OUTPUT_MAPPING,
            "variables": {"keyword": "keyword"},
        },
        "_keyword_default": keyword,
    }


async def generate_plan_with_llm(requirement: str, *, keyword: str | None = None) -> dict[str, Any]:
    from forge_agent.llm.protocol import chat

    tools = list_available_tools()
    tools_block = "\n".join(f"- {t}" for t in tools)
    prompt = f"""你是 forge-agent 架构师。根据用户需求设计多 Agent Pipeline（Mock 演示，mock_mode=true）。

用户需求：{requirement}

可用工具：
{tools_block}

template 只能用 scraper_agent。chief 固定 generic.chief。

输出严格 JSON：
{{
  "keyword": "提取的关键词",
  "pipeline_name": "Pipeline 名称",
  "agents": [{{"agent_id","name","template","config":{{"platform","tools","mock_mode":true,"mock_response","prompt","output_schema","output_mapping","variables":{{"keyword":"keyword"}}}}}}],
  "team": {{"mode":"parallel","chief_id":"generic.chief"}},
  "new_tools": []
}}
只输出 JSON。"""

    response = await chat(prompt, temperature=0.2)
    text = response.content.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    plan = json.loads(text)
    plan["requirement"] = requirement
    plan["planner"] = "llm"
    plan["keyword"] = extract_keyword(requirement, keyword or plan.get("keyword"))
    plan["pipeline_id"] = _slug_pipeline_id(requirement, plan["keyword"])
    plan.setdefault("pipeline_name", f"{plan['keyword']} 趋势分析")
    return _normalize_plan(plan)


async def generate_plan(
    requirement: str,
    *,
    keyword: str | None = None,
    use_llm: bool = False,
) -> dict[str, Any]:
    requirement = requirement.strip()
    if not requirement:
        raise ValueError("requirement is required")
    if use_llm:
        try:
            return await generate_plan_with_llm(requirement, keyword=keyword)
        except Exception:
            plan = generate_plan_rule_based(requirement, keyword=keyword)
            plan["planner"] = "rule_fallback"
            return plan
    return generate_plan_rule_based(requirement, keyword=keyword)


def _normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    keyword = plan.get("keyword", "labubu")
    agents: list[dict[str, Any]] = []
    for idx, agent in enumerate(plan.get("agents", [])):
        agent_id = str(agent.get("agent_id", f"agent_{idx}"))
        config = dict(agent.get("config", {}))
        config.setdefault("mock_mode", True)
        config.setdefault("mock_response", _mock_response(agent.get("name", agent_id)))
        config.setdefault(
            "prompt",
            DEFAULT_PROMPT_TEMPLATE.format(platform="平台", keyword="{keyword}", data="{data}"),
        )
        config.setdefault("output_schema", DEFAULT_OUTPUT_SCHEMA)
        config.setdefault("output_mapping", DEFAULT_OUTPUT_MAPPING)
        config.setdefault("variables", {"keyword": "keyword"})
        tools = config.get("tools") or []
        if isinstance(tools, str):
            config["tools"] = [tools]
        agents.append(
            {
                "agent_id": agent_id,
                "name": agent.get("name", agent_id),
                "domain": agent.get("domain", "generic"),
                "template": agent.get("template", "scraper_agent"),
                "tags": agent.get("tags", ["architect"]),
                "config": config,
            }
        )

    team = dict(plan.get("team", {}))
    team.setdefault("mode", "parallel")
    team.setdefault("chief_id", "generic.chief")

    return {
        "requirement": plan.get("requirement", ""),
        "keyword": keyword,
        "pipeline_id": plan.get("pipeline_id")
        or _slug_pipeline_id(plan.get("requirement", ""), keyword),
        "pipeline_name": plan.get("pipeline_name", f"{keyword} 趋势分析"),
        "planner": plan.get("planner", "rule"),
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
