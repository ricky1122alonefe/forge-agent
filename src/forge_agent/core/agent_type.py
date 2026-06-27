"""Agent type classification system (T2.1.1).

Defines the core agent types that determine code generation style and structure.
Each type has specific characteristics, use cases, and generation templates.

Usage::

    from forge_agent.core.agent_type import AgentType

    agent_type = AgentType.SCRAPER
    print(agent_type.description)  # "数据抓取类 — 从网页/API 获取结构化数据"
    print(agent_type.use_cases)    # ["爬取商品价格", "抓取新闻标题", ...]
"""
from __future__ import annotations

from enum import Enum


class AgentType(str, Enum):
    """Agent 类型枚举 — 决定生成代码的风格和结构。

    Types:
        SCRAPER: 数据抓取类 — 从网页/API 获取结构化数据
        ANALYZER: 数据分析类 — 处理数据并生成洞察
        MONITOR: 监控告警类 — 持续监控并在异常时告警
        GENERATOR: 内容生成类 — 生成文本/代码/报告
        GENERAL: 通用类 — 灵活的通用 Agent（默认）
    """

    SCRAPER = "scraper"
    ANALYZER = "analyzer"
    MONITOR = "monitor"
    GENERATOR = "generator"
    GENERAL = "general"

    @property
    def description(self) -> str:
        """返回类型的中文描述。"""
        descriptions = {
            "scraper": "数据抓取类 — 从网页/API 获取结构化数据",
            "analyzer": "数据分析类 — 处理数据并生成洞察",
            "monitor": "监控告警类 — 持续监控并在异常时告警",
            "generator": "内容生成类 — 生成文本/代码/报告",
            "general": "通用类 — 灵活的通用 Agent",
        }
        return descriptions.get(self.value, "未知类型")

    @property
    def use_cases(self) -> list[str]:
        """返回该类型的典型用例。"""
        cases = {
            "scraper": ["爬取商品价格", "抓取新闻标题", "提取 API 数据"],
            "analyzer": ["股票趋势分析", "用户行为分析", "情感分析"],
            "monitor": ["服务器监控", "价格波动监控", "系统健康检查"],
            "generator": ["生成周报", "代码生成", "内容创作"],
            "general": ["自定义任务", "多步骤工作流", "集成多个能力"],
        }
        return cases.get(self.value, [])

    @classmethod
    def from_string(cls, value: str) -> AgentType:
        """从字符串解析 AgentType（大小写不敏感）。

        Args:
            value: 类型字符串（如 "scraper", "SCRAPER", "Scraper"）

        Returns:
            对应的 AgentType 枚举值

        Raises:
            ValueError: 如果字符串不是有效的类型
        """
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        from forge_agent.exceptions import InvalidAgentTypeError
        raise InvalidAgentTypeError(value, [m.value for m in cls])

    @classmethod
    def default(cls) -> AgentType:
        """返回默认类型（GENERAL）。"""
        return cls.GENERAL
