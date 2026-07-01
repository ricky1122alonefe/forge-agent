"""Tests for LLM provider key resolution and error hints."""

from __future__ import annotations

import pytest

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.exceptions import LLMAuthError
from forge_agent.llm.providers.openai_compat import OpenAICompatibleClient


def test_openai_compat_missing_key_shows_env_hint(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cfg = ProviderConfig(
        provider_id="deepseek",
        type="deepseek",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
    )
    client = OpenAICompatibleClient(cfg)

    with pytest.raises(LLMAuthError) as exc_info:
        client._resolve_key()

    exc = exc_info.value
    assert "DEEPSEEK_API_KEY" in str(exc)
    assert "请设置环境变量" in exc.friendly()
    assert "export DEEPSEEK_API_KEY" in exc.friendly()
