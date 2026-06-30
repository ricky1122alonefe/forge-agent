"""AgentArchitect — generate a forge-agent pipeline from natural language.

Usage:
    cd /path/to/forge-agent
    python -m examples.toy_trend_demo.architect "分析 labubu 在微博和抖音的热度趋势"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from forge_agent.core import Mission, Team
from forge_agent.core.factory import AgentFactory
from forge_agent.core.runner import TeamRunner
from forge_agent.llm.protocol import chat

from .agents.scraper_agent import register_tool_agent
from .run import _mock_response
from .tools import register_all as register_trend_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


DEFAULT_PROMPT_TEMPLATE = (
    "你是一位{trend}趋势分析专家。请分析以下平台数据，"
    "判断关键词「{keyword}」相关的{trend}热度趋势。\n\n数据：\n{data}\n\n"
    "请输出 JSON："
    '{{"verdict": "lean_positive|lean_neutral|lean_negative|risk", '
    '"confidence": 0.0-1.0, "risk": 0.0-1.0, '
    '"evidence": ["关键发现1"], '
    '"recommended_action": "execute|watch|hold|alert", '
    '"metrics": {{}}}}'
)

DEFAULT_OUTPUT_SCHEMA = {
    "verdict": "str",
    "confidence": "float",
    "risk": "float",
    "evidence": "list[str]",
    "recommended_action": "str",
    "metrics": "dict",
}

DEFAULT_OUTPUT_MAPPING = {
    "verdict": "verdict",
    "confidence": "confidence",
    "risk": "risk",
    "evidence": "evidence",
    "recommended_action": "recommended_action",
    "metrics": "metrics",
}


async def _generate_plan(requirement: str, available_tools: list[str]) -> dict[str, Any]:
    """Turn a natural-language requirement into a pipeline plan."""
    try:
        return await _generate_plan_with_llm(requirement, available_tools)
    except Exception as exc:
        log.warning("LLM architect failed (%s), falling back to rule-based planner.", exc)
        return _generate_plan_rule_based(requirement, available_tools)


async def _generate_plan_with_llm(requirement: str, available_tools: list[str]) -> dict[str, Any]:
    """Ask an LLM to turn a natural-language requirement into a pipeline plan."""
    tools_block = "\n".join(f"- {t}" for t in available_tools) if available_tools else "- (none)"

    prompt = f"""你是一位 AI 系统架构师。请根据用户需求设计一个 forge-agent 多 agent pipeline。

用户需求：{requirement}

已有工具列表（agent 可以通过 ``tools`` 配置声明调用这些工具）：
{tools_block}

通用 verdict 值只能是：lean_positive / lean_neutral / lean_negative / risk
通用 recommended_action 值只能是：execute / watch / hold / alert

template 只允许使用：prompt_agent 或 scraper_agent（scraper_agent 是特殊的 prompt_agent，会自动调用 tools 获取数据）。

请输出一个严格的 JSON，包含：
- "domain": 业务领域，例如 "toy_trend"
- "keyword": 用户想分析的关键词/IP
- "agents": agent 配置列表，每个 agent 必须包含 agent_id, name, template, config（含 tools, prompt, output_schema, output_mapping, mock_mode=true, mock_response）
- "team": team 配置，包含 team_id, name, mode("parallel"|"sequential"), chief_id("generic.chief")
- "new_tools": 如果需要已有工具列表中没有的工具，请列出每个工具的名称和一句话描述（不需要写代码，我们会提示用户补充）

注意：
1. 只使用已有工具列表中的工具，不要编造工具名。
2. 如果用户没有明确关键词，请从需求中提取最可能的 IP/关键词。
3. mock_response 必须是合法 JSON 字符串，且 verdict/risk/confidence 字段齐全。

只输出 JSON，不要输出 markdown 代码块或其他说明。"""

    response = await chat(prompt, temperature=0.2)
    text = response.content.strip()

    # Strip markdown fences if the LLM wrapped the JSON.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Architect failed to parse LLM output as JSON:\n%s", text)
        raise RuntimeError(f"Invalid JSON from architect LLM: {exc}") from exc

    return _normalize_plan(plan)


def _generate_plan_rule_based(requirement: str, available_tools: list[str]) -> dict[str, Any]:
    """Fallback planner that uses simple keyword matching when no LLM is available."""
    keyword = _extract_keyword(requirement)
    domain = "toy_trend"

    tool_map = {
        "微博": "weibo.hot_search",
        "小红书": "xiaohongshu.search",
        "得物": "dewu.search",
    }

    agents: list[dict[str, Any]] = []
    for platform_name, tool_name in tool_map.items():
        if platform_name in requirement and tool_name in available_tools:
            agents.append(
                {
                    "agent_id": f"trend.{tool_name.split('.')[0]}",
                    "name": f"{platform_name}趋势专家",
                    "domain": domain,
                    "template": "scraper_agent",
                    "tags": ["generated", platform_name],
                    "config": {
                        "platform": tool_name.split(".")[0],
                        "tools": [tool_name],
                        "keyword_variable": "keyword",
                        "mock_mode": True,
                        "mock_response": _mock_response(platform_name, "lean_positive", 0.75, 0.2),
                        "prompt": DEFAULT_PROMPT_TEMPLATE.format(
                            trend=domain, keyword="{keyword}", data="{data}"
                        ),
                        "output_schema": DEFAULT_OUTPUT_SCHEMA,
                        "output_mapping": DEFAULT_OUTPUT_MAPPING,
                    },
                }
            )

    new_tools: list[dict[str, str]] = []
    known_platforms = set(tool_map)
    for platform in known_platforms:
        if platform in requirement and tool_map[platform] not in available_tools:
            new_tools.append(
                {"tool_name": tool_map[platform], "description": f"{platform} 搜索/热度抓取工具"}
            )

    if not agents:
        # Default: use weibo if nothing matched.
        agents.append(
            {
                "agent_id": "trend.weibo",
                "name": "微博热度专家",
                "domain": domain,
                "template": "scraper_agent",
                "tags": ["generated", "微博"],
                "config": {
                    "platform": "weibo",
                    "tools": ["weibo.hot_search"],
                    "keyword_variable": "keyword",
                    "mock_mode": True,
                    "mock_response": _mock_response("微博", "lean_positive", 0.75, 0.2),
                    "prompt": DEFAULT_PROMPT_TEMPLATE.format(
                        trend=domain, keyword="{keyword}", data="{data}"
                    ),
                    "output_schema": DEFAULT_OUTPUT_SCHEMA,
                    "output_mapping": DEFAULT_OUTPUT_MAPPING,
                },
            }
        )

    return _normalize_plan(
        {
            "domain": domain,
            "keyword": keyword,
            "agents": agents,
            "team": {
                "team_id": "generated_team",
                "name": "Generated Trend Team",
                "mode": "parallel",
                "chief_id": "generic.chief",
            },
            "new_tools": new_tools,
        }
    )


def _extract_keyword(requirement: str) -> str:
    """Extract a keyword/IP from the requirement using simple heuristics."""
    # Try to find a quoted or emphasized term.
    import re

    quotes = re.findall(r"[「『]([^」』]+)[」』]", requirement)
    if quotes:
        return quotes[0]

    # Common toy/IP names in Chinese/English mixed text.
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}|[一-龥]{2,10}", requirement)
    skip = {"分析", "趋势", "热度", "潮玩", "微博", "小红书", "得物", "抖音", "平台"}
    for c in candidates:
        if c not in skip and len(c) >= 2:
            return c

    return "labubu"


def _normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Sanitize and fill defaults for the LLM-generated plan."""
    domain = plan.get("domain", "toy_trend")
    keyword = plan.get("keyword", "labubu")

    agents: list[dict[str, Any]] = []
    for idx, agent in enumerate(plan.get("agents", [])):
        agent_id = agent.get("agent_id", f"generated.agent_{idx}")
        name = agent.get("name", agent_id)
        template = agent.get("template", "scraper_agent")
        config: dict[str, Any] = dict(agent.get("config", {}))

        # Ensure every agent has a prompt and mock response for offline demo.
        if "prompt" not in config:
            config["prompt"] = DEFAULT_PROMPT_TEMPLATE.format(
                trend=domain, keyword="{keyword}", data="{data}"
            )
        if "output_schema" not in config:
            config["output_schema"] = DEFAULT_OUTPUT_SCHEMA
        if "output_mapping" not in config:
            config["output_mapping"] = DEFAULT_OUTPUT_MAPPING
        if "mock_mode" not in config:
            config["mock_mode"] = True
        if "mock_response" not in config:
            config["mock_response"] = _mock_response(name, "lean_positive", 0.75, 0.2)
        if "keyword_variable" not in config:
            config["keyword_variable"] = "keyword"

        # Validate declared tools exist; if not, fall back to no tools.
        declared_tools = config.get("tools") or []
        if isinstance(declared_tools, str):
            declared_tools = [declared_tools]
        config["tools"] = declared_tools

        agents.append(
            {
                "agent_id": agent_id,
                "name": name,
                "domain": domain,
                "template": template,
                "tags": agent.get("tags", ["generated"]),
                "config": config,
            }
        )

    team = plan.get("team", {})
    team.setdefault("team_id", "generated_team")
    team.setdefault("name", "Generated Team")
    team.setdefault("mode", "parallel")
    team.setdefault("chief_id", "generic.chief")
    team.setdefault("domain", domain)

    return {
        "domain": domain,
        "keyword": keyword,
        "agents": agents,
        "team": team,
        "new_tools": plan.get("new_tools", []),
    }


async def build_and_run(
    requirement: str,
    *,
    keyword: str | None = None,
    save_path: str | None = None,
) -> None:
    """Generate a pipeline from a requirement and execute it."""
    factory = AgentFactory()
    factory.register_template("scraper_agent", register_tool_agent)

    # Register existing scraping tools so the architect can reason about them.
    register_trend_tools()
    from forge_agent.mcp.gateway import get_gateway

    available_tools = get_gateway().list_tools()

    plan = await _generate_plan(requirement, available_tools)
    generated_keyword = keyword or plan["keyword"]

    log.info(
        "Architect generated plan: domain=%s keyword=%s agents=%s",
        plan["domain"],
        generated_keyword,
        [a["agent_id"] for a in plan["agents"]],
    )
    if plan["new_tools"]:
        log.warning(
            "The plan requires tools not currently available: %s",
            [t["tool_name"] for t in plan["new_tools"]],
        )
        log.warning("Please implement these tools under examples/toy_trend_demo/tools/ and re-run.")

    # Optionally persist the generated plan.
    if save_path:
        import yaml

        save_file = Path(save_path)
        save_file.parent.mkdir(parents=True, exist_ok=True)
        with save_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"agents": plan["agents"], "team": plan["team"]},
                f,
                allow_unicode=True,
                sort_keys=False,
            )
        log.info("Saved generated plan to %s", save_file)

    # Build agents from the generated dict configs.
    for agent_cfg in plan["agents"]:
        factory.from_dict(agent_cfg)

    team_cfg = plan["team"]
    team = Team(
        team_id=team_cfg["team_id"],
        name=team_cfg["name"],
        domain=team_cfg["domain"],
        agent_ids=[a["agent_id"] for a in plan["agents"]],
        chief_id=team_cfg.get("chief_id"),
        mode=team_cfg["mode"],
    )

    mission = Mission(
        mission_id=f"generated_{team.team_id}_{generated_keyword}",
        name=f"{generated_keyword} - {team.name}",
        description=requirement,
        team=team,
        payload={"keyword": generated_keyword},
    )

    board = await TeamRunner().run(mission)

    print("=" * 60)
    print("Generated Mission:", mission.name)
    print("=" * 60)
    print("\n--- Generated Agents ---")
    for report in board.agents:
        raw_data = report.raw.get("data", {})
        scraped_items = len(raw_data.get("items", []))
        data_source = "real" if raw_data.get("note") != "mock data" else "mock"
        print(
            f"\n[{report.name}] platform={report.raw.get('platform')} "
            f"verdict={report.verdict.value} confidence={report.confidence:.0%} risk={report.risk:.0%}"
        )
        print(f"  data: {data_source}, scraped_items: {scraped_items}")
        for ev in report.evidence:
            print(f"  - {ev}")

    print("\n--- Chief Summary ---")
    chief_report = board.summary.get("chief_report")
    if chief_report:
        print(f"verdict: {chief_report.get('verdict')}")
        print(f"confidence: {chief_report.get('confidence')}")
        print(f"risk: {chief_report.get('risk')}")
        print(f"recommended_action: {chief_report.get('recommended_action')}")
        print("evidence:")
        for ev in chief_report.get("evidence", []):
            print(f"  - {ev}")
    else:
        print("No chief report produced.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AgentArchitect — generate and run a pipeline from a requirement"
    )
    parser.add_argument(
        "requirement", help="Natural language requirement, e.g. '分析 labubu 在微博和抖音的热度'"
    )
    parser.add_argument("--keyword", help="Override the keyword/IP extracted from the requirement")
    parser.add_argument(
        "--save",
        default="examples/toy_trend_demo/generated/plan.yaml",
        help="Path to save the generated plan",
    )
    args = parser.parse_args()

    asyncio.run(build_and_run(args.requirement, keyword=args.keyword, save_path=args.save))


if __name__ == "__main__":
    main()
