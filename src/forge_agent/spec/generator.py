"""AgentSpecGenerator — requirement → AgentSpec (rule-first, LLM optional)."""

from __future__ import annotations

import re
from typing import Any

from forge_agent.spec.models import AgentPrimitive, AgentSpec, MockCase, SchemaProfile
from forge_agent.spec.schema_profiles import (
    ANALYSIS_MAPPING,
    ANALYSIS_SCHEMA,
    GENERATE_MAPPING,
    GENERATE_SCHEMA,
    MONITOR_MAPPING,
    MONITOR_SCHEMA,
    analysis_mock_response,
    generate_mock_response,
    monitor_mock_response,
    search_mock_response,
    synthesizer_mock_response,
)
from forge_agent.spec.tool_match import match_platforms

ANALYSIS_EXPECT_KEYS = ["verdict", "confidence", "risk", "evidence", "recommended_action"]
MONITOR_EXPECT_KEYS = ["alert", "severity", "message", "recommended_action"]

SYNTHESIZER_KEYWORDS = ["汇总", "综合", "上游", "多份报告", "synthesize", "combine reports"]
SEARCH_KEYWORDS = ["搜索", "查询", "search", "look up", "检索", "rss", "feed", "订阅"]
MONITOR_KEYWORDS = [
    "监控",
    "告警",
    "阈值",
    "monitor",
    "alert",
    "threshold",
    "同比",
    "异常",
    "黑名单",
    "白名单",
    "规则",
]
GENERATE_KEYWORDS = ["润色", "改写", "撰写", "compose", "write", "创作", "generate content"]
FETCH_KEYWORDS = ["抓取", "爬取", "scrape", "fetch", "热搜", "平台", "api", "拉取", "拉数"]

PROFILE_KEYWORDS: dict[SchemaProfile, list[str]] = {
    SchemaProfile.SENTIMENT: ["情感", "sentiment", "评论情绪"],
    SchemaProfile.SUMMARY: ["摘要", "summary", "总结", "概括"],
    SchemaProfile.EXTRACT: ["抽取", "提取", "实体", "extract"],
    SchemaProfile.COMPARE: ["对比", "比较", "差异", "compare"],
    SchemaProfile.RISK: ["风险", "risk", "评级"],
}

TYPE_ID_TO_PRIMITIVE: dict[str, AgentPrimitive] = {
    "scraper": AgentPrimitive.FETCHER,
    "search": AgentPrimitive.SEARCHER,
    "synthesizer": AgentPrimitive.SYNTHESIZER,
    "analyzer": AgentPrimitive.REASONER,
    "reasoner": AgentPrimitive.REASONER,
    "monitor": AgentPrimitive.MONITOR,
    "generator": AgentPrimitive.GENERATOR,
}


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
        "微博",
        "小红书",
        "得物",
        "抖音",
        "平台",
        "搜索",
        "监控",
        "摘要",
    }
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


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k in text or k in lower for k in keywords)


def detect_schema_profile(requirement: str) -> SchemaProfile:
    for profile, keywords in PROFILE_KEYWORDS.items():
        if _contains_any(requirement, keywords):
            return profile
    return SchemaProfile.ANALYSIS


def detect_primitive(requirement: str) -> AgentPrimitive:
    if _contains_any(requirement, SYNTHESIZER_KEYWORDS):
        return AgentPrimitive.SYNTHESIZER
    if _contains_any(requirement, MONITOR_KEYWORDS):
        return AgentPrimitive.MONITOR
    if _contains_any(requirement, SEARCH_KEYWORDS):
        return AgentPrimitive.SEARCHER
    if _contains_any(requirement, GENERATE_KEYWORDS):
        return AgentPrimitive.GENERATOR
    if match_platforms(requirement) or _contains_any(requirement, FETCH_KEYWORDS):
        return AgentPrimitive.FETCHER
    return AgentPrimitive.REASONER


def _primitive_from_type_id(type_id: str) -> AgentPrimitive:
    return TYPE_ID_TO_PRIMITIVE.get(type_id, AgentPrimitive.REASONER)


def _profile_prompt(profile: SchemaProfile, topic: str) -> str:
    prompts = {
        SchemaProfile.SENTIMENT: "对主题「{topic}」相关文本做情感分类。\n输出 JSON：verdict, confidence, risk, evidence, recommended_action, metrics。",
        SchemaProfile.SUMMARY: "对主题「{topic}」相关内容生成摘要。\n输出 JSON：verdict, confidence, risk, evidence, recommended_action, metrics。",
        SchemaProfile.EXTRACT: "从主题「{topic}」相关内容抽取实体。\n输出 JSON：verdict, confidence, risk, evidence, recommended_action, metrics。",
        SchemaProfile.COMPARE: "对比主题「{topic}」相关的两份数据。\n输出 JSON：verdict, confidence, risk, evidence, recommended_action, metrics。",
        SchemaProfile.RISK: "评估主题「{topic}」的风险等级。\n输出 JSON：verdict, confidence, risk, evidence, recommended_action, metrics。",
        SchemaProfile.ANALYSIS: "分析主题「{topic}」并给出结构化建议。\n输出 JSON：verdict, confidence, risk, evidence, recommended_action, metrics。",
    }
    return prompts.get(profile, prompts[SchemaProfile.ANALYSIS])


def _default_mock_cases(
    primitive: AgentPrimitive,
    params: dict[str, Any],
    profile: SchemaProfile = SchemaProfile.ANALYSIS,
) -> list[MockCase]:
    if primitive == AgentPrimitive.FETCHER:
        kw = str(params.get("keyword", "demo"))
        return [
            MockCase(name="default", input={"keyword": kw}, expect_keys=list(ANALYSIS_EXPECT_KEYS))
        ]
    if primitive == AgentPrimitive.SEARCHER:
        q = str(params.get("query", params.get("keyword", "demo")))
        return [
            MockCase(name="default", input={"query": q}, expect_keys=list(ANALYSIS_EXPECT_KEYS))
        ]
    if primitive == AgentPrimitive.SYNTHESIZER:
        return [
            MockCase(
                name="with_upstream",
                input={"reports": [{"agent_id": "a1", "verdict": "lean_positive"}]},
                expect_keys=list(ANALYSIS_EXPECT_KEYS),
            )
        ]
    if primitive == AgentPrimitive.MONITOR:
        threshold = float(params.get("threshold", 100))
        return [
            MockCase(
                name="default",
                input={
                    "current_value": 42,
                    "threshold": threshold,
                    "metric_name": params.get("metric_name", "metric"),
                },
                expect_keys=list(MONITOR_EXPECT_KEYS),
            )
        ]
    if primitive == AgentPrimitive.GENERATOR:
        topic = str(params.get("topic", "demo"))
        return [
            MockCase(
                name="default",
                input={"topic": topic, "format": params.get("format", "markdown")},
                expect_keys=["content", "summary", "recommended_action"],
            )
        ]
    topic = str(params.get("topic", params.get("keyword", "demo")))
    return [
        MockCase(name="default", input={"topic": topic}, expect_keys=list(ANALYSIS_EXPECT_KEYS))
    ]


def generate_spec_rule_based(
    requirement: str,
    *,
    agent_id: str | None = None,
    keyword: str | None = None,
    focus: str | None = None,
    primitive: AgentPrimitive | None = None,
) -> AgentSpec:
    req = requirement.strip()
    if not req:
        raise ValueError("requirement is required")

    detected = detect_primitive(req)
    primitive = primitive or detected
    profile = (
        detect_schema_profile(req)
        if primitive == AgentPrimitive.REASONER
        else SchemaProfile.ANALYSIS
    )
    if focus == "summary":
        profile = SchemaProfile.SUMMARY
    elif focus == "extract":
        profile = SchemaProfile.EXTRACT

    kw = extract_keyword(req, keyword)
    name = _guess_name(req, primitive)
    aid = agent_id or _slug_agent_id(f"{primitive.value}_{kw}")

    builders = {
        AgentPrimitive.FETCHER: lambda: _build_fetcher_spec(req, aid, name, kw),
        AgentPrimitive.SEARCHER: lambda: _build_searcher_spec(req, aid, name, kw),
        AgentPrimitive.SYNTHESIZER: lambda: _build_synthesizer_spec(
            req, aid, name, focus or "general"
        ),
        AgentPrimitive.MONITOR: lambda: _build_monitor_spec(req, aid, name, kw),
        AgentPrimitive.GENERATOR: lambda: _build_generator_spec(req, aid, name, kw),
        AgentPrimitive.REASONER: lambda: _build_reasoner_spec(req, aid, name, profile, kw),
    }
    spec = builders[primitive]()
    from forge_agent.spec.capabilities import apply_requirement_capabilities

    return apply_requirement_capabilities(spec, req)


def _guess_name(requirement: str, primitive: AgentPrimitive) -> str:
    labels = {
        AgentPrimitive.FETCHER: "数据抓取",
        AgentPrimitive.SEARCHER: "搜索分析",
        AgentPrimitive.SYNTHESIZER: "报告汇总",
        AgentPrimitive.MONITOR: "指标监控",
        AgentPrimitive.GENERATOR: "内容生成",
        AgentPrimitive.REASONER: "智能分析",
    }
    kw = extract_keyword(requirement)
    return f"{kw} {labels[primitive]}"


def _build_fetcher_spec(req: str, agent_id: str, name: str, keyword: str) -> AgentSpec:
    platforms = match_platforms(req)
    if not platforms:
        from forge_agent.spec.tool_match import PlatformMatch

        platforms = [PlatformMatch(label="微博", platform="weibo", tool_name="weibo.hot_search")]

    primary = platforms[0]
    tool_names = [p.tool_name for p in platforms]
    prompt = (
        f"你是一位趋势分析专家。请分析以下 {primary.label} 等平台数据，"
        f"判断关键词「{{keyword}}」相关的热度趋势。\n\n数据：\n{{data}}\n\n"
        "请输出 JSON，包含 verdict、confidence、risk、evidence、recommended_action、metrics。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="scraper_agent",
        primitive=AgentPrimitive.FETCHER,
        schema_profile=SchemaProfile.ANALYSIS,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "platform": primary.platform,
            "tools": tool_names,
            "prompt": prompt,
            "mock_response": analysis_mock_response(primary.label),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"keyword": "keyword"},
        },
        mock_cases=[
            MockCase(
                name="default", input={"keyword": keyword}, expect_keys=list(ANALYSIS_EXPECT_KEYS)
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
        schema_profile=SchemaProfile.ANALYSIS,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "query_template": "{query}",
            "search_backend": "mock",
            "mock_results": [
                {"title": f"{keyword} 结果 1", "snippet": "Mock snippet"},
                {"title": f"{keyword} 结果 2", "snippet": "Mock snippet"},
            ],
            "prompt": prompt,
            "mock_response": search_mock_response(),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"query": "query"},
        },
        mock_cases=[
            MockCase(
                name="default", input={"query": keyword}, expect_keys=list(ANALYSIS_EXPECT_KEYS)
            )
        ],
    )


def _build_synthesizer_spec(req: str, agent_id: str, name: str, focus: str) -> AgentSpec:
    prompt = (
        "你是高级分析师。请基于以下上游 Agent 报告做汇总评估。\n"
        f"关注维度：{focus}\n\n报告：\n{{reports}}\n\n"
        "请输出 JSON，包含 verdict、confidence、risk、 evidence、recommended_action、metrics。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="prompt_agent",
        primitive=AgentPrimitive.SYNTHESIZER,
        schema_profile=SchemaProfile.ANALYSIS,
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
                        {"agent_id": "a1", "verdict": "lean_positive", "evidence": ["mock"]}
                    ]
                },
                expect_keys=list(ANALYSIS_EXPECT_KEYS),
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
        schema_profile=SchemaProfile.MONITOR,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "prompt": prompt,
            "mock_response": monitor_mock_response(),
            "output_schema": MONITOR_SCHEMA,
            "output_mapping": MONITOR_MAPPING,
            "variables": {"current_value": "current_value", "threshold": "threshold"},
        },
        mock_cases=[
            MockCase(
                name="default",
                input={"current_value": 42, "threshold": 100},
                expect_keys=list(MONITOR_EXPECT_KEYS),
            )
        ],
    )


def _build_generator_spec(req: str, agent_id: str, name: str, keyword: str) -> AgentSpec:
    prompt = (
        "你是专业写作者。主题：{topic}，格式：{format}。\n"
        "请输出 JSON：content、format、summary、recommended_action。"
    )
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="prompt_agent",
        primitive=AgentPrimitive.GENERATOR,
        schema_profile=SchemaProfile.GENERATE,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "prompt": prompt,
            "mock_response": generate_mock_response(),
            "output_schema": GENERATE_SCHEMA,
            "output_mapping": GENERATE_MAPPING,
            "variables": {"topic": "topic", "format": "format"},
        },
        mock_cases=[
            MockCase(
                name="default",
                input={"topic": keyword, "format": "markdown"},
                expect_keys=["content", "summary", "recommended_action"],
            )
        ],
    )


def _build_reasoner_spec(
    req: str, agent_id: str, name: str, profile: SchemaProfile, keyword: str
) -> AgentSpec:
    return AgentSpec(
        agent_id=agent_id,
        name=name,
        template="prompt_agent",
        primitive=AgentPrimitive.REASONER,
        schema_profile=profile,
        description=req,
        requirement=req,
        config={
            "mock_mode": True,
            "prompt": _profile_prompt(profile, keyword),
            "mock_response": analysis_mock_response(profile.value),
            "output_schema": ANALYSIS_SCHEMA,
            "output_mapping": ANALYSIS_MAPPING,
            "variables": {"topic": "topic"},
        },
        mock_cases=[
            MockCase(
                name="default", input={"topic": keyword}, expect_keys=list(ANALYSIS_EXPECT_KEYS)
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
    if use_llm and llm_chat is not None:
        try:
            from forge_agent.generator.requirements import RequirementsParser

            parser = RequirementsParser(llm_chat=llm_chat)
            parsed = await parser.parse(requirement)
            hints = _hints_from_requirements(parsed)
            spec = generate_spec_rule_based(
                requirement,
                agent_id=agent_id or hints.get("agent_id"),
                keyword=keyword or hints.get("keyword"),
                focus=focus or hints.get("focus"),
                primitive=hints.get("primitive"),
            )
            spec.planner = "llm_assisted"
            if parsed.description:
                spec.description = parsed.description
            return spec
        except Exception:
            spec = generate_spec_rule_based(
                requirement,
                agent_id=agent_id,
                keyword=keyword,
                focus=focus,
            )
            spec.planner = "rule_fallback"
            return spec
    spec = generate_spec_rule_based(requirement, agent_id=agent_id, keyword=keyword, focus=focus)
    spec.planner = "rule"
    return spec


def _hints_from_requirements(parsed: Any) -> dict[str, Any]:
    """Map RequirementsParser output to AgentSpec generation hints."""
    from forge_agent.core.agent_type import AgentType

    hints: dict[str, Any] = {}
    if parsed.agent_id:
        hints["agent_id"] = parsed.agent_id

    for field in getattr(parsed, "inputs", []) or []:
        name = getattr(field, "name", "")
        example = getattr(field, "example", None)
        if example and name in {"keyword", "query", "topic", "payload"}:
            hints["keyword"] = str(example)
            break

    req = getattr(parsed, "raw_requirement", "") or ""
    if any(k in req for k in SYNTHESIZER_KEYWORDS):
        hints["primitive"] = AgentPrimitive.SYNTHESIZER
    elif "search" in getattr(parsed, "capabilities_required", []):
        hints["primitive"] = AgentPrimitive.SEARCHER
    else:
        type_map = {
            AgentType.SCRAPER: AgentPrimitive.FETCHER,
            AgentType.ANALYZER: AgentPrimitive.REASONER,
            AgentType.MONITOR: AgentPrimitive.MONITOR,
            AgentType.GENERATOR: AgentPrimitive.GENERATOR,
        }
        agent_type = getattr(parsed, "agent_type", None)
        if agent_type in type_map:
            hints["primitive"] = type_map[agent_type]

    if any(k in req for k in PROFILE_KEYWORDS[SchemaProfile.SUMMARY]):
        hints["focus"] = "summary"
    elif any(k in req for k in PROFILE_KEYWORDS[SchemaProfile.EXTRACT]):
        hints["focus"] = "extract"

    return hints
