"""Google Gemini client (stub for v0.2, full impl in v0.3)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.exceptions import LLMError
from forge_agent.llm.protocol import (
    ChatMessage,
    LLMClient,
    LLMResponse,
    StreamChunk,
)

log = logging.getLogger(__name__)


class GeminiClient(LLMClient):
    """Stub: use `pip install google-generativeai` to enable."""

    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg

    @property
    def provider_id(self) -> str:
        return self.cfg.provider_id

    async def chat(self, messages, **kwargs) -> LLMResponse:
        raise LLMError(
            "Gemini provider not yet implemented in forge-agent v0.2. "
            "Use the OpenAI-compatible endpoint or upgrade to v0.3.",
            provider=self.provider_id,
        )

    async def stream(self, messages, **kwargs) -> AsyncIterator[StreamChunk]:
        raise LLMError("Gemini not implemented in v0.2", provider=self.provider_id)
        yield StreamChunk(delta="", provider="", model="")
