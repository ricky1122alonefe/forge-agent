"""Tests for the unified forge-agent exception hierarchy and friendly hints."""

from __future__ import annotations

from forge_agent.exceptions import (
    ConfigError,
    ConfigValidationError,
    ForgeAgentError,
    ForgeError,
    LLMError,
    ProviderNotConfiguredError,
    ToolError,
)
from forge_agent.llm.exceptions import LLMAuthError


def test_forge_agent_error_is_forge_error() -> None:
    assert issubclass(ForgeAgentError, ForgeError)


def test_config_validation_error_is_config_error() -> None:
    exc = ConfigValidationError(["missing required field: agent_id"])
    assert isinstance(exc, ConfigError)
    assert isinstance(exc, ForgeError)
    assert "missing required field: agent_id" in str(exc)
    assert "请检查" in exc.friendly()


def test_llm_auth_error_friendly_includes_hint() -> None:
    exc = LLMAuthError(
        "API key for 'deepseek' not found.",
        provider="deepseek",
        hint="请设置环境变量 DEEPSEEK_API_KEY",
    )
    assert isinstance(exc, LLMError)
    assert "请设置环境变量 DEEPSEEK_API_KEY" in exc.friendly()


def test_provider_not_configured_error_friendly() -> None:
    exc = ProviderNotConfiguredError("deepseek", available=["ollama"])
    assert "deepseek" in exc.friendly()
    assert "forge-agent llm set" in exc.friendly()


def test_tool_error_is_forge_error() -> None:
    assert issubclass(ToolError, ForgeError)
