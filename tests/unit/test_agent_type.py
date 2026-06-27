"""Tests for AgentType enum (T2.1.1).

Covers:
- Enum values (5 types)
- Description property
- Use cases property
- Default type
- String serialization
- from_string parsing
"""
from __future__ import annotations

import pytest

from forge_agent.core.agent_type import AgentType


# ------------------------------------------------------------------ Enum values

def test_agent_type_has_five_types() -> None:
    """AgentType should have exactly 5 types."""
    assert len(AgentType) == 5


def test_agent_type_values() -> None:
    """All expected types should exist."""
    expected = {"scraper", "analyzer", "monitor", "generator", "general"}
    actual = {t.value for t in AgentType}
    assert actual == expected


def test_agent_type_scraper() -> None:
    """SCRAPER type should exist."""
    assert AgentType.SCRAPER.value == "scraper"


def test_agent_type_analyzer() -> None:
    """ANALYZER type should exist."""
    assert AgentType.ANALYZER.value == "analyzer"


def test_agent_type_monitor() -> None:
    """MONITOR type should exist."""
    assert AgentType.MONITOR.value == "monitor"


def test_agent_type_generator() -> None:
    """GENERATOR type should exist."""
    assert AgentType.GENERATOR.value == "generator"


def test_agent_type_general() -> None:
    """GENERAL type should exist."""
    assert AgentType.GENERAL.value == "general"


# ------------------------------------------------------------------ Description

def test_description_scraper() -> None:
    """SCRAPER should have a description."""
    desc = AgentType.SCRAPER.description
    assert "数据抓取" in desc
    assert "网页" in desc or "API" in desc


def test_description_analyzer() -> None:
    """ANALYZER should have a description."""
    desc = AgentType.ANALYZER.description
    assert "数据分析" in desc


def test_description_monitor() -> None:
    """MONITOR should have a description."""
    desc = AgentType.MONITOR.description
    assert "监控" in desc


def test_description_generator() -> None:
    """GENERATOR should have a description."""
    desc = AgentType.GENERATOR.description
    assert "生成" in desc


def test_description_general() -> None:
    """GENERAL should have a description."""
    desc = AgentType.GENERAL.description
    assert "通用" in desc


def test_all_types_have_description() -> None:
    """All types should have non-empty descriptions."""
    for agent_type in AgentType:
        assert agent_type.description
        assert len(agent_type.description) > 5


# ------------------------------------------------------------------ Use cases

def test_use_cases_scraper() -> None:
    """SCRAPER should have use cases."""
    cases = AgentType.SCRAPER.use_cases
    assert len(cases) >= 2
    assert any("爬取" in c or "抓取" in c for c in cases)


def test_use_cases_analyzer() -> None:
    """ANALYZER should have use cases."""
    cases = AgentType.ANALYZER.use_cases
    assert len(cases) >= 2
    assert any("分析" in c for c in cases)


def test_use_cases_monitor() -> None:
    """MONITOR should have use cases."""
    cases = AgentType.MONITOR.use_cases
    assert len(cases) >= 2
    assert any("监控" in c for c in cases)


def test_use_cases_generator() -> None:
    """GENERATOR should have use cases."""
    cases = AgentType.GENERATOR.use_cases
    assert len(cases) >= 2
    assert any("生成" in c for c in cases)


def test_use_cases_general() -> None:
    """GENERAL should have use cases."""
    cases = AgentType.GENERAL.use_cases
    assert len(cases) >= 2


def test_all_types_have_use_cases() -> None:
    """All types should have non-empty use cases."""
    for agent_type in AgentType:
        assert agent_type.use_cases
        assert len(agent_type.use_cases) >= 2


# ------------------------------------------------------------------ Default

def test_default_type() -> None:
    """Default type should be GENERAL."""
    assert AgentType.default() == AgentType.GENERAL


def test_default_is_general() -> None:
    """default() should return GENERAL."""
    default = AgentType.default()
    assert default.value == "general"


# ------------------------------------------------------------------ String serialization

def test_enum_is_string() -> None:
    """AgentType should be a string enum."""
    assert isinstance(AgentType.SCRAPER, str)


def test_enum_value_is_string() -> None:
    """Enum values should be strings."""
    for agent_type in AgentType:
        assert isinstance(agent_type.value, str)


def test_json_serialization() -> None:
    """AgentType should serialize to JSON-friendly strings."""
    import json

    data = {"type": AgentType.SCRAPER.value}
    serialized = json.dumps(data)
    assert '"scraper"' in serialized


# ------------------------------------------------------------------ from_string

def test_from_string_lowercase() -> None:
    """Should parse lowercase strings."""
    assert AgentType.from_string("scraper") == AgentType.SCRAPER
    assert AgentType.from_string("analyzer") == AgentType.ANALYZER
    assert AgentType.from_string("monitor") == AgentType.MONITOR
    assert AgentType.from_string("generator") == AgentType.GENERATOR
    assert AgentType.from_string("general") == AgentType.GENERAL


def test_from_string_uppercase() -> None:
    """Should parse uppercase strings."""
    assert AgentType.from_string("SCRAPER") == AgentType.SCRAPER
    assert AgentType.from_string("ANALYZER") == AgentType.ANALYZER


def test_from_string_mixed_case() -> None:
    """Should parse mixed case strings."""
    assert AgentType.from_string("Scraper") == AgentType.SCRAPER
    assert AgentType.from_string("Analyzer") == AgentType.ANALYZER


def test_from_string_with_whitespace() -> None:
    """Should strip whitespace."""
    assert AgentType.from_string("  scraper  ") == AgentType.SCRAPER
    assert AgentType.from_string("\tmonitor\n") == AgentType.MONITOR


def test_from_string_invalid() -> None:
    """Should raise ValueError for invalid types."""
    with pytest.raises(ValueError, match="Invalid agent type"):
        AgentType.from_string("invalid")


def test_from_string_empty() -> None:
    """Should raise ValueError for empty strings."""
    with pytest.raises(ValueError, match="Invalid agent type"):
        AgentType.from_string("")


def test_from_string_error_message() -> None:
    """Error message should list valid types."""
    with pytest.raises(ValueError) as exc_info:
        AgentType.from_string("invalid")

    error_msg = str(exc_info.value)
    assert "scraper" in error_msg
    assert "analyzer" in error_msg
    assert "monitor" in error_msg
    assert "generator" in error_msg
    assert "general" in error_msg


# ------------------------------------------------------------------ Enum behavior

def test_enum_comparison() -> None:
    """Should support equality comparison."""
    assert AgentType.SCRAPER == AgentType.SCRAPER
    assert AgentType.SCRAPER != AgentType.ANALYZER


def test_enum_in_set() -> None:
    """Should work in sets."""
    types = {AgentType.SCRAPER, AgentType.ANALYZER}
    assert AgentType.SCRAPER in types
    assert AgentType.MONITOR not in types


def test_enum_as_dict_key() -> None:
    """Should work as dictionary keys."""
    config = {
        AgentType.SCRAPER: {"timeout": 30},
        AgentType.MONITOR: {"interval": 60},
    }
    assert config[AgentType.SCRAPER]["timeout"] == 30


def test_enum_iteration() -> None:
    """Should support iteration."""
    types = list(AgentType)
    assert len(types) == 5
    assert AgentType.SCRAPER in types
    assert AgentType.GENERAL in types
