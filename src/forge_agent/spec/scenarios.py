"""20-scenario acceptance matrix for AgentSpec generator (AGENT_PLAN A2.5)."""

from __future__ import annotations

from dataclasses import dataclass

from forge_agent.spec.models import AgentPrimitive, SchemaProfile


@dataclass(frozen=True)
class ScenarioCase:
    scenario_id: str
    requirement: str
    expected_primitive: AgentPrimitive
    keyword: str | None = None
    focus: str | None = None
    expected_profile: SchemaProfile | None = None


SCENARIO_MATRIX: list[ScenarioCase] = [
    ScenarioCase("S01", "分析 labubu 在微博的热度趋势", AgentPrimitive.FETCHER, keyword="labubu"),
    ScenarioCase(
        "S02", "分析 popmart 在微博和小红书的热度", AgentPrimitive.FETCHER, keyword="popmart"
    ),
    ScenarioCase("S03", "监控竞品价格在得物的变化", AgentPrimitive.MONITOR, keyword="竞品价格"),
    ScenarioCase(
        "S04",
        "对行业新闻做摘要分析",
        AgentPrimitive.REASONER,
        expected_profile=SchemaProfile.SUMMARY,
    ),
    ScenarioCase("S05", "通过 API 拉取数据并分析趋势", AgentPrimitive.FETCHER, keyword="metrics"),
    ScenarioCase(
        "S06",
        "从网页内容抽取关键实体",
        AgentPrimitive.REASONER,
        expected_profile=SchemaProfile.EXTRACT,
    ),
    ScenarioCase("S07", "搜索 AI 芯片行业动态并回答", AgentPrimitive.SEARCHER, keyword="AI芯片"),
    ScenarioCase("S08", "搜索 RSS 订阅源并生成摘要", AgentPrimitive.SEARCHER, keyword="RSS"),
    ScenarioCase(
        "S09",
        "对用户评论做情感分类",
        AgentPrimitive.REASONER,
        expected_profile=SchemaProfile.SENTIMENT,
    ),
    ScenarioCase(
        "S10", "评估项目风险等级", AgentPrimitive.REASONER, expected_profile=SchemaProfile.RISK
    ),
    ScenarioCase(
        "S11",
        "对长文文档生成 executive summary",
        AgentPrimitive.REASONER,
        expected_profile=SchemaProfile.SUMMARY,
    ),
    ScenarioCase(
        "S12",
        "从文本中抽取公司名和产品名",
        AgentPrimitive.REASONER,
        expected_profile=SchemaProfile.EXTRACT,
    ),
    ScenarioCase(
        "S13",
        "对比两份表格数据的差异",
        AgentPrimitive.REASONER,
        expected_profile=SchemaProfile.COMPARE,
    ),
    ScenarioCase("S14", "润色并改写营销报告", AgentPrimitive.GENERATOR, keyword="营销报告"),
    ScenarioCase("S15", "汇总上游多份 Agent 报告并给出综合结论", AgentPrimitive.SYNTHESIZER),
    ScenarioCase("S16", "当库存低于阈值 100 时告警", AgentPrimitive.MONITOR),
    ScenarioCase("S17", "检测销售额同比异常波动", AgentPrimitive.MONITOR, keyword="销售额"),
    ScenarioCase("S18", "检查关键词是否命中黑名单规则", AgentPrimitive.MONITOR, keyword="spam"),
    ScenarioCase("S19", "根据指标给出 execute watch hold 建议", AgentPrimitive.REASONER),
    ScenarioCase("S20", "分析数据并输出结构化建议", AgentPrimitive.REASONER),
]
