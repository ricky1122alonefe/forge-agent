"""Ollama client (local LLM, no API key required).

Speaks the OpenAI-compatible chat completions API (Ollama >= 0.5 supports this),
so it can reuse OpenAICompatibleClient — we just subclass for special handling
(no key required, model list endpoint).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.providers.openai_compat import OpenAICompatibleClient
from forge_agent.llm.protocol import (
    ChatMessage,
    LLMResponse,
    StreamChunk,
)

log = logging.getLogger(__name__)


class OllamaClient(OpenAICompatibleClient):
    """Ollama client. No API key needed; uses 'ollama' as a placeholder."""

    def _resolve_key(self) -> str:
        return "ollama"  # Ollama doesn't need auth

    async def list_local_models(self) -> list[str]:
        """Hit Ollama's /api/tags to list installed models."""
        import httpx
        base = (self.cfg.base_url or "http://localhost:11434/v1").rstrip("/")
        tags_url = base.replace("/v1", "") + "/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(tags_url)
                r.raise_for_status()
                data = r.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:  # noqa: BLE001
            log.warning("Failed to list Ollama models (is it running?)", exc_info=True)
            return []
