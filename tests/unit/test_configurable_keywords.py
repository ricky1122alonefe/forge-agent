"""Tests for configurable keywords in RequirementsParser."""

from __future__ import annotations

from forge_agent.core.agent_type import AgentType
from forge_agent.generator.requirements import RequirementsParser


class TestConfigurableKeywords:
    """Test that keyword mappings are configurable via register_*() API."""

    def setup_method(self):
        # Reset to defaults before each test
        RequirementsParser.DOMAIN_KEYWORDS = {
            "stock": ["股票", "股价", "stock", "share", "nvda", "tsla"],
            "football": ["球赛", "足球", "比赛", "match", "football", "world cup"],
            "social": ["舆情", "微博", "twitter", "social", "评论", "评论"],
            "office": ["办公", "邮件", "邮件", "email", "office", "日程"],
            "ecommerce": ["商品", "订单", "电商", "product", "order"],
        }
        RequirementsParser.AGENT_TYPE_KEYWORDS = {
            "scraper": ["抓取", "爬取", "scrape", "crawl", "fetch", "采集"],
            "analyzer": ["分析", "analyze", "统计", "insight", "洞察"],
            "monitor": ["监控", "monitor", "告警", "alert", "watch", "检测"],
            "generator": ["生成", "generate", "create", "写", "compose", "创作"],
        }
        RequirementsParser.COMMON_CAPABILITIES = {
            "search": ["搜索", "search", "查询", "look up", "find"],
            "llm": ["大模型", "llm", "ai", "智能", "推理"],
            "prompt_manager": ["prompt", "提示词", "提示"],
            "memory": ["记忆", "memory", "历史", "history"],
        }

    # ------------------------------------------------------------------ Domain

    def test_register_new_domain(self):
        RequirementsParser.register_domain("healthcare", ["医疗", "医院", "health"])
        assert "healthcare" in RequirementsParser.DOMAIN_KEYWORDS
        assert "医疗" in RequirementsParser.DOMAIN_KEYWORDS["healthcare"]

    def test_register_extends_existing_domain(self):
        RequirementsParser.register_domain("stock", ["a股", "港股"])
        assert "a股" in RequirementsParser.DOMAIN_KEYWORDS["stock"]
        assert "股票" in RequirementsParser.DOMAIN_KEYWORDS["stock"]  # original still there

    def test_register_domain_no_duplicates(self):
        original_count = len(RequirementsParser.DOMAIN_KEYWORDS["stock"])
        RequirementsParser.register_domain("stock", ["股票"])  # already exists
        assert len(RequirementsParser.DOMAIN_KEYWORDS["stock"]) == original_count

    def test_guess_domain_uses_class_attribute(self):
        RequirementsParser.register_domain("healthcare", ["医疗", "医院"])
        parser = RequirementsParser()
        result = parser._parse_heuristic("帮我做一个医疗数据分析的agent")
        assert result.domain == "healthcare"

    def test_guess_domain_default_generic(self):
        parser = RequirementsParser()
        result = parser._parse_heuristic("做一个通用的agent")
        assert result.domain == "generic"

    # ------------------------------------------------------------------ Agent Type

    def test_register_new_agent_type(self):
        RequirementsParser.register_agent_type_keywords(
            "translator", ["翻译", "translate", "翻译器"]
        )
        assert "translator" in RequirementsParser.AGENT_TYPE_KEYWORDS

    def test_register_extends_existing_agent_type(self):
        RequirementsParser.register_agent_type_keywords("scraper", ["download", "下载"])
        assert "download" in RequirementsParser.AGENT_TYPE_KEYWORDS["scraper"]
        assert "抓取" in RequirementsParser.AGENT_TYPE_KEYWORDS["scraper"]

    def test_guess_agent_type_uses_class_attribute(self):
        parser = RequirementsParser()
        result = parser._parse_heuristic("帮我抓取网页数据")
        assert result.agent_type == AgentType.SCRAPER

    def test_guess_agent_type_default_general(self):
        parser = RequirementsParser()
        result = parser._parse_heuristic("做一个agent")
        assert result.agent_type == AgentType.GENERAL

    # ------------------------------------------------------------------ Capability

    def test_register_new_capability(self):
        RequirementsParser.register_capability("database", ["数据库", "database", "sql"])
        assert "database" in RequirementsParser.COMMON_CAPABILITIES

    def test_register_extends_existing_capability(self):
        RequirementsParser.register_capability("search", ["检索", "retrieval"])
        assert "检索" in RequirementsParser.COMMON_CAPABILITIES["search"]
        assert "搜索" in RequirementsParser.COMMON_CAPABILITIES["search"]

    def test_guess_capabilities_uses_class_attribute(self):
        RequirementsParser.register_capability("database", ["数据库", "sql"])
        parser = RequirementsParser()
        result = parser._parse_heuristic("帮我做一个数据库查询的agent")
        assert "database" in result.capabilities_required

    # ------------------------------------------------------------------ Integration

    def test_full_parse_with_custom_keywords(self):
        RequirementsParser.register_domain("healthcare", ["医疗", "医院", "health"])
        RequirementsParser.register_capability("database", ["数据库", "sql"])
        parser = RequirementsParser()
        result = parser._parse_heuristic("帮我做一个医疗数据库查询的agent，需要搜索功能")
        assert result.domain == "healthcare"
        assert "database" in result.capabilities_required
        assert "search" in result.capabilities_required
