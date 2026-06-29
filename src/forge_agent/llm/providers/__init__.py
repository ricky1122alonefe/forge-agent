"""LLM provider implementations.

All providers implement the same LLMClient Protocol. The OpenAI-compatible
base class covers 90% of providers (DeepSeek, Moonshot, Doubao, Qwen, etc.).
"""

from __future__ import annotations

import logging

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.protocol import LLMClient

log = logging.getLogger(__name__)


def build_client(cfg: ProviderConfig) -> LLMClient:
    """Dispatch to the right provider implementation based on cfg.type."""
    return build_client_from_type(cfg)


def build_client_from_type(cfg: ProviderConfig) -> LLMClient:
    ptype = (cfg.type or cfg.provider_id).lower()

    if ptype in {
        "deepseek",
        "openai",
        "moonshot",
        "kimi",
        "doubao",
        "qwen",
        "zhipu",
        "baichuan",
        "openai_compatible",
    }:
        from forge_agent.llm.providers.openai_compat import OpenAICompatibleClient

        return OpenAICompatibleClient(cfg)

    if ptype == "ollama":
        from forge_agent.llm.providers.ollama import OllamaClient

        return OllamaClient(cfg)

    if ptype == "anthropic" or ptype == "claude":
        from forge_agent.llm.providers.anthropic import AnthropicClient

        return AnthropicClient(cfg)

    if ptype == "gemini":
        from forge_agent.llm.providers.gemini import GeminiClient

        return GeminiClient(cfg)

    if ptype == "mock":
        from forge_agent.llm.providers.mock import MockClient

        return MockClient(cfg)

    # Default fallback: OpenAI-compatible (covers most providers)
    log.warning("Unknown provider type %r; falling back to OpenAI-compatible", ptype)
    from forge_agent.llm.providers.openai_compat import OpenAICompatibleClient

    return OpenAICompatibleClient(cfg)


__all__ = ["LLMClient", "build_client", "build_client_from_type"]
