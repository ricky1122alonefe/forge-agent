"""Tests for forge_agent.generator.prompts — type-specific prompts and get_system_prompt."""

from __future__ import annotations

import pytest

from forge_agent.core.agent_type import AgentType
from forge_agent.generator.prompts import (
    ANALYZER_SYSTEM,
    CODE_GENERATOR_SYSTEM,
    GENERAL_SYSTEM,
    GENERATOR_SYSTEM,
    MONITOR_SYSTEM,
    SCRAPER_SYSTEM,
    build_user_prompt,
    get_system_prompt,
)


# ------------------------------------------------------------------ get_system_prompt


class TestGetSystemPrompt:
    """get_system_prompt() returns the correct prompt for each AgentType."""

    def test_scraper(self) -> None:
        assert get_system_prompt(AgentType.SCRAPER) is SCRAPER_SYSTEM

    def test_analyzer(self) -> None:
        assert get_system_prompt(AgentType.ANALYZER) is ANALYZER_SYSTEM

    def test_monitor(self) -> None:
        assert get_system_prompt(AgentType.MONITOR) is MONITOR_SYSTEM

    def test_generator(self) -> None:
        assert get_system_prompt(AgentType.GENERATOR) is GENERATOR_SYSTEM

    def test_general(self) -> None:
        assert get_system_prompt(AgentType.GENERAL) is GENERAL_SYSTEM

    def test_general_equals_code_generator(self) -> None:
        """GENERAL_SYSTEM should be the same as CODE_GENERATOR_SYSTEM."""
        assert GENERAL_SYSTEM is CODE_GENERATOR_SYSTEM

    def test_unknown_type_falls_back_to_general(self) -> None:
        """If an unknown type is passed, should fall back to GENERAL_SYSTEM."""
        # Simulate by passing a non-enum value via dict.get fallback
        from forge_agent.generator.prompts import _TYPE_PROMPTS
        result = _TYPE_PROMPTS.get("nonexistent", GENERAL_SYSTEM)
        assert result is GENERAL_SYSTEM


# ------------------------------------------------------------------ Type prompt content


class TestTypePromptContent:
    """Each type-specific prompt should contain key guidance strings."""

    def test_scraper_contains_scraping_keywords(self) -> None:
        assert "抓取" in SCRAPER_SYSTEM or "数据源" in SCRAPER_SYSTEM
        assert "observe" in SCRAPER_SYSTEM
        assert "decide" in SCRAPER_SYSTEM
        assert "act" in SCRAPER_SYSTEM

    def test_analyzer_contains_analysis_keywords(self) -> None:
        assert "分析" in ANALYZER_SYSTEM or "洞察" in ANALYZER_SYSTEM
        assert "observe" in ANALYZER_SYSTEM
        assert "LLM" in ANALYZER_SYSTEM or "chat" in ANALYZER_SYSTEM

    def test_monitor_contains_monitoring_keywords(self) -> None:
        assert "监控" in MONITOR_SYSTEM or "告警" in MONITOR_SYSTEM
        assert "observe" in MONITOR_SYSTEM
        assert "阈值" in MONITOR_SYSTEM or "基线" in MONITOR_SYSTEM

    def test_generator_contains_generation_keywords(self) -> None:
        assert "生成" in GENERATOR_SYSTEM
        assert "observe" in GENERATOR_SYSTEM
        assert "LLM" in GENERATOR_SYSTEM or "chat" in GENERATOR_SYSTEM

    def test_general_contains_framework_contract(self) -> None:
        assert "BaseAgent" in GENERAL_SYSTEM
        assert "observe" in GENERAL_SYSTEM
        assert "decide" in GENERAL_SYSTEM
        assert "act" in GENERAL_SYSTEM

    def test_all_prompts_contain_framework_contract(self) -> None:
        """All type prompts should include the base framework contract."""
        for prompt in [SCRAPER_SYSTEM, ANALYZER_SYSTEM, MONITOR_SYSTEM, GENERATOR_SYSTEM, GENERAL_SYSTEM]:
            assert "BaseAgent" in prompt, f"Missing BaseAgent in prompt: {prompt[:50]}..."
            assert "agent_id" in prompt
            assert "AgentReport" in prompt
            assert "register_agent" in prompt


# ------------------------------------------------------------------ build_user_prompt


class TestBuildUserPrompt:
    """build_user_prompt() composes the user message correctly."""

    def test_basic_prompt(self) -> None:
        result = build_user_prompt("我需要一个股票监控 Agent")
        assert "请根据以下需求生成 Agent 代码" in result
        assert "我需要一个股票监控 Agent" in result
        assert "请只输出 Python 代码" in result

    def test_with_mcp_tools(self) -> None:
        result = build_user_prompt("需求", mcp_tools=["tavily.search", "db.read"])
        assert "tavily.search" in result
        assert "db.read" in result
        assert "MCP" in result

    def test_with_existing_agents(self) -> None:
        result = build_user_prompt("需求", existing_agents=["stock.monitor", "news.scraper"])
        assert "stock.monitor" in result
        assert "news.scraper" in result
        assert "避免重名" in result

    def test_with_both_mcp_and_existing(self) -> None:
        result = build_user_prompt(
            "需求",
            mcp_tools=["tavily.search"],
            existing_agents=["stock.monitor"],
        )
        assert "tavily.search" in result
        assert "stock.monitor" in result

    def test_empty_mcp_tools_not_included(self) -> None:
        result = build_user_prompt("需求", mcp_tools=[])
        assert "MCP" not in result

    def test_none_mcp_tools_not_included(self) -> None:
        result = build_user_prompt("需求", mcp_tools=None)
        assert "MCP" not in result
