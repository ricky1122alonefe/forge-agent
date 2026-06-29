"""Tests for T2.1.4 — CodeGenerator template selection by AgentType."""

from __future__ import annotations

import pytest

from forge_agent.core.agent_type import AgentType
from forge_agent.generator.templates import (
    clear_cache,
    get_template,
    list_templates,
)


@pytest.fixture(autouse=True)
def _clear_template_cache():
    """Clear template cache before each test."""
    clear_cache()
    yield
    clear_cache()


# ------------------------------------------------------------------ get_template


class TestGetTemplate:
    """get_template() loads the correct template for each AgentType."""

    def test_scraper_template_exists(self) -> None:
        tmpl = get_template(AgentType.SCRAPER)
        assert tmpl is not None
        assert "ScraperAgent" in tmpl or "scraper" in tmpl.lower()

    def test_analyzer_template_exists(self) -> None:
        tmpl = get_template(AgentType.ANALYZER)
        assert tmpl is not None
        assert "AnalyzerAgent" in tmpl or "analyzer" in tmpl.lower()

    def test_monitor_template_exists(self) -> None:
        tmpl = get_template(AgentType.MONITOR)
        assert tmpl is not None
        assert "MonitorAgent" in tmpl or "monitor" in tmpl.lower()

    def test_generator_template_exists(self) -> None:
        tmpl = get_template(AgentType.GENERATOR)
        assert tmpl is not None
        assert "GeneratorAgent" in tmpl or "generator" in tmpl.lower()

    def test_general_template_exists(self) -> None:
        tmpl = get_template(AgentType.GENERAL)
        assert tmpl is not None
        assert "GeneralAgent" in tmpl or "general" in tmpl.lower()

    def test_template_is_cached(self) -> None:
        tmpl1 = get_template(AgentType.SCRAPER)
        tmpl2 = get_template(AgentType.SCRAPER)
        assert tmpl1 is tmpl2  # Same object reference

    def test_template_contains_base_agent_import(self) -> None:
        for at in AgentType:
            tmpl = get_template(at)
            assert tmpl is not None
            assert "BaseAgent" in tmpl, f"Template for {at.value} missing BaseAgent"

    def test_template_contains_three_methods(self) -> None:
        for at in AgentType:
            tmpl = get_template(at)
            assert tmpl is not None
            assert "observe" in tmpl, f"Template for {at.value} missing observe"
            assert "decide" in tmpl, f"Template for {at.value} missing decide"
            assert "act" in tmpl, f"Template for {at.value} missing act"

    def test_template_contains_agent_report(self) -> None:
        for at in AgentType:
            tmpl = get_template(at)
            assert tmpl is not None
            assert "AgentReport" in tmpl, f"Template for {at.value} missing AgentReport"

    def test_template_has_class_vars(self) -> None:
        for at in AgentType:
            tmpl = get_template(at)
            assert tmpl is not None
            assert "agent_id" in tmpl, f"Template for {at.value} missing agent_id"
            assert "name" in tmpl, f"Template for {at.value} missing name"
            assert "domain" in tmpl, f"Template for {at.value} missing domain"
            assert "version" in tmpl, f"Template for {at.value} missing version"


# ------------------------------------------------------------------ list_templates


class TestListTemplates:
    """list_templates() reports which types have template files."""

    def test_all_types_have_templates(self) -> None:
        result = list_templates()
        for at in AgentType:
            assert at in result
            assert result[at] is True, f"Missing template for {at.value}"

    def test_returns_dict(self) -> None:
        result = list_templates()
        assert isinstance(result, dict)
        assert len(result) == len(AgentType)


# ------------------------------------------------------------------ Template content


class TestTemplateContent:
    """Each template should have type-specific characteristics."""

    def test_scraper_has_http_keywords(self) -> None:
        tmpl = get_template(AgentType.SCRAPER)
        assert tmpl is not None
        # Should reference data fetching concepts
        assert any(kw in tmpl for kw in ["search", "url", "fetch", "data", "request"])

    def test_analyzer_has_llm_keywords(self) -> None:
        tmpl = get_template(AgentType.ANALYZER)
        assert tmpl is not None
        assert "chat" in tmpl or "llm" in tmpl.lower()

    def test_monitor_has_threshold_keywords(self) -> None:
        tmpl = get_template(AgentType.MONITOR)
        assert tmpl is not None
        assert any(kw in tmpl for kw in ["threshold", "alert", "baseline", "monitor"])

    def test_generator_has_generation_keywords(self) -> None:
        tmpl = get_template(AgentType.GENERATOR)
        assert tmpl is not None
        assert any(kw in tmpl for kw in ["generate", "content", "chat", "topic"])

    def test_monitor_has_memory_usage(self) -> None:
        tmpl = get_template(AgentType.MONITOR)
        assert tmpl is not None
        assert "memory" in tmpl

    def test_all_templates_are_valid_python(self) -> None:
        """Templates should be syntactically valid Python."""
        import ast

        for at in AgentType:
            tmpl = get_template(at)
            assert tmpl is not None
            try:
                ast.parse(tmpl)
            except SyntaxError as e:
                pytest.fail(f"Template for {at.value} has syntax error: {e}")


# ------------------------------------------------------------------ build_user_prompt with template


class TestBuildUserPromptWithTemplate:
    """build_user_prompt() correctly includes template in the prompt."""

    def test_template_included_in_prompt(self) -> None:
        from forge_agent.generator.prompts import build_user_prompt

        tmpl = "class MyAgent(BaseAgent): ..."
        result = build_user_prompt("需求规格", template=tmpl)
        assert "参考以下代码骨架" in result
        assert "class MyAgent(BaseAgent): ..." in result

    def test_no_template_no_reference_section(self) -> None:
        from forge_agent.generator.prompts import build_user_prompt

        result = build_user_prompt("需求规格")
        assert "参考以下代码骨架" not in result

    def test_template_with_mcp_tools(self) -> None:
        from forge_agent.generator.prompts import build_user_prompt

        tmpl = "class MyAgent: ..."
        result = build_user_prompt("需求", template=tmpl, mcp_tools=["tavily.search"])
        assert "参考以下代码骨架" in result
        assert "tavily.search" in result
