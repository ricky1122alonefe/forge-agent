"""AgentSpecGenerator — requirement → AgentSpec (rule-first, LLM optional)."""

from __future__ import annotations

import re
from typing import Any

from forge_agent.agent_spec.models import AgentPrimitive, AgentSpec, MockCase
from forge_agent.agent_spec.schema_profiles import (
    ANALYSIS_MAPPING,
    ANALYSIS_SCHEMA,
    MONITOR_MAPPING,
    MONITOR_SCHEMA,
    analysis_mock_response,
    monitor_mock_response,
    search_mock_response,
    synthesizer_mock_response,
)
from forge_agent.builtin.tools import register_builtin_tools
from forge_agent.platform.tool_registry import get_tool_registry

PLATFORM_RULES: list[tuple[str, str, str]] = [
    ("微博", "weibo", "weibo.hot_search"),
    ("小红书", "xiaohongshu", "xiaohongshu.search"),
    ("得物", "dewu", "dewu.search"),
    ("抖音", "douyin", "douyin.hot"),
]

SYNTHESIZER_KEYWORDS = ["汇总", "综合", "上游", "多份报告", "synthesize", "combine reports"]
SEARCH_KEYWORDS = ["搜索", "查询", "search", "look up", "检索"]
MONITOR_KEYWORDS = ["监控", "告警", "阈值", "monitor", "alert", "threshold"]
GENERATE_KEYWORDS = ["生成", "撰写", "compose", "write", "创作", "generate content"]
FETCH_KEYWORDS = ["抓取", "爬取", "scrape", "fetch", "热搜", "平台"]


def extract_keyword(requirement: str, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    quotes = re.findall(r"[「『\"']([^」』\"']+)[」』\"']", requirement)
    if quotes:
        return quotes[0].strip()
    skip = {"分析", "趋势", "热度", "微博", "小红书", "得物", "抖音", "平台", "搜索", "监控"}
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", requirement)
    for match in latin:
        if match.lower() not in skip:
            return match
    for match in re.findall(r"[一-龥]{2,12}", requirement):
        if match not in skip:
            return match
    return "demo"


def _slug_agent_id(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", name.lower()).strip("_")
    return base or "generated_agent"


def _detect_platform(requirement: str) -> tuple[str, str, str] | None:
    register_builtin_tools()
    tools = set(get_tool_registry().list_names())
    for label, platform, tool_name in PLATFORM_RULES:
        if label in requirement and tool_name in tools:
            return label, platform, tool_name
    if any(k in requirement for k in ("微博", "weibo")) and "weibo.hot_search" in tools:
        return "微博", "weibo", "weibo.hot_search"
    return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k in text or k in lower for k in keywords)


def detect_primitive(requirement: str) -> AgentPrimitive:
    if _contains_any(requirement, SYNTHESIZER_KEYWORDS):
        return AgentPrimitive.SYNTHESIZER
    if _contains_any(requirement, MONITOR_KEYWORDS):
        return AgentPrimitive.MONITOR
    if _contains_any(requirement, GENERATE_KEYWORDS):
        return AgentPrimitive.REASONER
    if _detect_platform(requirement) or _contains_any(requirement, FETCH_KEYWORDS):
        return AgentPrimitive.FETCHER
    if _contains_any(requirement, SEARCH_KEYWORDS):
        return AgentPrimitive.SEARCHER
    if _contains_any(requirement, ["分析", "analyze", "评估", "判断"]):
        return AgentPrimitive.REASONER
    return AgentPrimitive.REASONER


def generate_spec_rule_based(
    requirement: str,
    *,
    agent_id: str | None = None,
    keyword: str | None = None,
    focus: str | None = None,
) -> AgentSpec:
    """Build an AgentSpec without calling an LLM."""
    req = requirement.strip()
    if not req:
        raise ValueError("requirement is required")

    primitive = detect_primitive(req)
    kw = extract_keyword(req, keyword)
    name = _guess_name(req, primitive)
    aid = agent_id or _slug_agent_id(name)

    if primitive == AgentPrimitive.FETCHER:
        return _build_fetcher_spec(req, aid, name, kw)
    if primitive == AgentPrimitive.SEARCHER:
        return _build_searcher_spec(req, aid, name, kw)
    if primitive == AgentPrimitive.SYNTHESIZER:
        return _build_synthesizer_spec(req, aid, name, focus or "general")
    if primitive == AgentPrimitive.MONITOR:
        return _build_monitor_spec(req, aid, name, kw)
    return _build_reasoner_spec(req, aid, name, focus or "general", kw)


def _guess_name(requirement: str, primitive: AgentPrimitive) -> str:
    labels = {
        AgentPrimitive.FETCHER: "数据抓取",
        AgentPrimitive.SEARCHER: "搜索分析",
        AgentPrimitive.SYNTHESIZER: "报告汇总",
        AgentPrimitive.MONITOR: "指标监控",
        AgentPrimitive.REASONER: "智能分析",
    }
    kw = extract_keyword(requirement)
    return f"{kw} {labels[primitive]}"


def _build_fetcher_spec(req: str, agent_id: str, name: str, keyword: str) -> AgentSpec:
    platform_info = _detect_platform(req) or ("微博", "weibo", "weibo.hot_search")
    label, platform, tool_name = platform_info
    prompt = (
        f"你是一位趋势分析专家。请分析以下 {label} 数据，"
        f"判断关键词「{{keyword}}」相关的热度趋势。\n\n数据：\n{{data}}\n\n"
        "请输出 JSON，包含 verdict、confidence、risk、evidence、recommended_action、metrics。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="scraper_agent",
        primitive=AgentPrimitive.FETCHER,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "platform": platform,
            "tools": [tool_name],
            "prompt": prompt,
            "mock_response": analysis_mock_response(label),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"keyword": "keyword"},
        },
        mock_cases=[
            MockCase(
                name="default",
                input={"keyword": keyword},
                expect_keys=["verdict", "confidence", "evidence"],
            )
        ],
    )


def _build_searcher_spec(req: str, agent_id: str, name: str, keyword: str) -> AgentSpec:
    prompt = (
        "你是研究分析专家。根据以下搜索结果，对主题「{query}」给出结构化判断。\n\n"
        "搜索结果（{n_results} 条）：\n{search_results}\n\n"
        "请输出 JSON，包含 verdict、confidence、risk、evidence、recommended_action、metrics。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="search_agent",
        primitive=AgentPrimitive.SEARCHER,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "query_template": "{query}",
            "search_backend": "mock",
            "mock_results": [
                {"title": f"{keyword} 行业动态", "snippet": "Mock 搜索结果 1"},
                {"title": f"{keyword} 市场观察", "snippet": "Mock 搜索结果 2"},
            ],
            "prompt": prompt,
            "mock_response": search_mock_response(),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"query": "query"},
        },
        mock_cases=[
            MockCase(
                name="default",
                input={"query": keyword},
                expect_keys=["verdict", "confidence"],
            )
        ],
    )


def _build_synthesizer_spec(req: str, agent_id: str, name: str, focus: str) -> AgentSpec:
    prompt = (
        "你是高级分析师。请基于以下上游 Agent 报告做汇总评估。\n"
        f"关注维度：{focus}\n\n报告：\n{{reports}}\n\n"
        "请输出 JSON，包含 verdict、confidence、risk、evidence、recommended_action、metrics。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="prompt_agent",
        primitive=AgentPrimitive.SYNTHESIZER,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "prompt": prompt,
            "mock_response": synthesizer_mock_response(),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"reports": "reports"},
        },
        mock_cases=[
            MockCase(
                name="with_upstream",
                input={
                    "reports": [
                        {"agent_id": "a1", "verdict": "lean_positive", "evidence": ["mock"]},
                    ]
                },
                expect_keys=["verdict", "confidence"],
            )
        ],
    )


def _build_monitor_spec(req: str, agent_id: str, name: str, keyword: str) -> AgentSpec:
    prompt = (
        f"你是监控 Agent。指标：{keyword}。当前值：{{current_value}}，阈值：{{threshold}}。\n"
        "请输出 JSON：alert、severity、threshold、current_value、message、recommended_action。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="prompt_agent",
        primitive=AgentPrimitive.MONITOR,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "prompt": prompt,
            "mock_response": monitor_mock_response(),
            "output_schema": MONITOR_SCHEMA,
            "output_mapping": MONITOR_MAPPING,
            "variables": {
                "current_value": "current_value",
                "threshold": "threshold",
            },
        },
        mock_cases=[
            MockCase(
                name="default",
                input={"current_value": 42, "threshold": 100},
                expect_keys=["alert", "severity", "message"],
            )
        ],
    )


def _build_reasoner_spec(req: str, agent_id: str, name: str, focus: str, keyword: str) -> AgentSpec:
    prompt = (
        f"你是分析专家。关注：{focus}。主题：{{topic}}。\n"
        "请输出 JSON，包含 verdict、confidence、risk、evidence、recommended_action、metrics。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="prompt_agent",
        primitive=AgentPrimitive.REASONER,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "prompt": prompt,
            "mock_response": analysis_mock_response("分析"),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"topic": "topic"},
        },
        mock_cases=[
            MockCase(
                name="default",
                input={"topic": keyword},
                expect_keys=["verdict", "confidence"],
            )
        ],
    )


async def generate_spec(
    requirement: str,
    *,
    agent_id: str | None = None,
    keyword: str | None = None,
    focus: str | None = None,
    use_llm: bool = False,
    llm_chat: Any = None,
) -> AgentSpec:
    """Generate an AgentSpec (rule-based by default)."""
    if use_llm and llm_chat is not None:
        try:
            from forge_agent.generator.requirements import RequirementsParser

            parser = RequirementsParser(llm_chat=llm_chat)
            parsed = await parser.parse(requirement)
            spec = generate_spec_rule_based(
                requirement,
                agent_id=agent_id or parsed.agent_id,
                keyword=keyword,
                focus=focus,
            )
            spec.planner = "llm_assisted"
            return spec
        except Exception:
            pass
    return generate_spec_rule_based(requirement, agent_id=agent_id, keyword=keyword, focus=focus)
