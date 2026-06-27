"""Tests for T2.1.2 — AgentRequirements agent_type field."""

from __future__ import annotations

import pytest

from forge_agent.core.agent_type import AgentType
from forge_agent.generator.requirements import (
    AgentRequirements,
    FieldSpec,
    RequirementsParser,
)


# ------------------------------------------------------------------ Helpers

def _make_req(**overrides: object) -> AgentRequirements:
    defaults = {
        "agent_id": "test.agent",
        "name": "Test Agent",
        "domain": "generic",
        "description": "A test agent",
    }
    defaults.update(overrides)
    return AgentRequirements(**defaults)  # type: ignore[arg-type]


# ------------------------------------------------------------------ agent_type field

class TestAgentTypeField:
    def test_default_is_general(self):
        req = _make_req()
        assert req.agent_type == AgentType.GENERAL

    def test_set_scraper(self):
        req = _make_req(agent_type=AgentType.SCRAPER)
        assert req.agent_type == AgentType.SCRAPER

    def test_set_analyzer(self):
        req = _make_req(agent_type=AgentType.ANALYZER)
        assert req.agent_type == AgentType.ANALYZER

    def test_set_monitor(self):
        req = _make_req(agent_type=AgentType.MONITOR)
        assert req.agent_type == AgentType.MONITOR

    def test_set_generator(self):
        req = _make_req(agent_type=AgentType.GENERATOR)
        assert req.agent_type == AgentType.GENERATOR


# ------------------------------------------------------------------ to_dict

class TestToDict:
    def test_includes_agent_type(self):
        req = _make_req(agent_type=AgentType.SCRAPER)
        d = req.to_dict()
        assert "agent_type" in d
        assert d["agent_type"] == "scraper"

    def test_default_agent_type_in_dict(self):
        req = _make_req()
        d = req.to_dict()
        assert d["agent_type"] == "general"

    def test_all_types_serialize(self):
        for t in AgentType:
            req = _make_req(agent_type=t)
            d = req.to_dict()
            assert d["agent_type"] == t.value


# ------------------------------------------------------------------ to_prompt

class TestToPrompt:
    def test_includes_type_line(self):
        req = _make_req(agent_type=AgentType.MONITOR)
        prompt = req.to_prompt()
        assert "Type: monitor" in prompt

    def test_includes_type_description(self):
        req = _make_req(agent_type=AgentType.SCRAPER)
        prompt = req.to_prompt()
        assert "scraper" in prompt
        assert "数据抓取" in prompt

    def test_general_type_in_prompt(self):
        req = _make_req()
        prompt = req.to_prompt()
        assert "Type: general" in prompt


# ------------------------------------------------------------------ RequirementsParser heuristic

class TestHeuristicParser:
    def setup_method(self):
        self.parser = RequirementsParser()

    def test_scraper_keywords(self):
        for text in ["抓取商品价格", "爬取新闻标题", "scrape website data", "采集数据"]:
            req = self.parser._parse_heuristic(text)
            assert req.agent_type == AgentType.SCRAPER, f"Failed for: {text}"

    def test_analyzer_keywords(self):
        for text in ["分析股票趋势", "analyze user behavior", "统计销售数据", "洞察市场"]:
            req = self.parser._parse_heuristic(text)
            assert req.agent_type == AgentType.ANALYZER, f"Failed for: {text}"

    def test_monitor_keywords(self):
        for text in ["监控服务器状态", "monitor stock prices", "告警系统", "检测异常"]:
            req = self.parser._parse_heuristic(text)
            assert req.agent_type == AgentType.MONITOR, f"Failed for: {text}"

    def test_generator_keywords(self):
        for text in ["生成周报", "generate report", "创作文章", "写代码"]:
            req = self.parser._parse_heuristic(text)
            assert req.agent_type == AgentType.GENERATOR, f"Failed for: {text}"

    def test_general_fallback(self):
        req = self.parser._parse_heuristic("做一个有用的工具")
        assert req.agent_type == AgentType.GENERAL

    def test_empty_input(self):
        req = self.parser._parse_heuristic("")
        assert req.agent_type == AgentType.GENERAL


# ------------------------------------------------------------------ RequirementsParser._from_dict

class TestFromDict:
    def setup_method(self):
        self.parser = RequirementsParser()

    def test_parses_agent_type(self):
        data = {
            "agent_id": "stock.monitor",
            "name": "Stock Monitor",
            "domain": "stock",
            "description": "Monitor stock prices",
            "agent_type": "monitor",
        }
        req = self.parser._from_dict(data, raw="monitor stocks")
        assert req.agent_type == AgentType.MONITOR

    def test_default_general_when_missing(self):
        data = {
            "agent_id": "test.agent",
            "name": "Test",
            "domain": "generic",
            "description": "test",
        }
        req = self.parser._from_dict(data, raw="test")
        assert req.agent_type == AgentType.GENERAL

    def test_invalid_type_falls_back_to_general(self):
        data = {
            "agent_id": "test.agent",
            "name": "Test",
            "domain": "generic",
            "description": "test",
            "agent_type": "invalid_type_xyz",
        }
        req = self.parser._from_dict(data, raw="test")
        assert req.agent_type == AgentType.GENERAL

    def test_case_insensitive_type(self):
        data = {
            "agent_id": "test.agent",
            "name": "Test",
            "domain": "generic",
            "description": "test",
            "agent_type": "SCRAPER",
        }
        req = self.parser._from_dict(data, raw="test")
        assert req.agent_type == AgentType.SCRAPER

    def test_all_types_parse(self):
        for t in AgentType:
            data = {
                "agent_id": "test.agent",
                "name": "Test",
                "domain": "generic",
                "description": "test",
                "agent_type": t.value,
            }
            req = self.parser._from_dict(data, raw="test")
            assert req.agent_type == t


# ------------------------------------------------------------------ Async parse

class TestAsyncParse:
    @pytest.mark.asyncio
    async def test_heuristic_parse(self):
        parser = RequirementsParser()
        req = await parser.parse("监控比特币价格变动")
        assert req.agent_type == AgentType.MONITOR

    @pytest.mark.asyncio
    async def test_heuristic_scraper(self):
        parser = RequirementsParser()
        req = await parser.parse("抓取淘宝商品价格")
        assert req.agent_type == AgentType.SCRAPER
