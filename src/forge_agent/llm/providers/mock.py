"""Mock LLM client — deterministic responses for tests and offline dev."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.protocol import (
    ChatMessage,
    LLMClient,
    LLMResponse,
    StreamChunk,
)


class MockClient(LLMClient):
    """A canned-response client. Useful for tests and offline demos.

    Configure the response via cfg.extra["response"] or by passing kwargs.
    """

    DEFAULT_RESPONSE = (
        "This is a mock response. Configure me via cfg.extra['response'] "
        "or pass response=... when constructing."
    )

    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg
        self._default = (cfg.extra or {}).get("response", self.DEFAULT_RESPONSE)
        # In-memory log of all calls (for assertions in tests)
        self.calls: list[dict[str, Any]] = []

    @property
    def provider_id(self) -> str:
        return self.cfg.provider_id

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append({
            "messages": [m.to_dict() if isinstance(m, ChatMessage) else m for m in messages],
            "model": model or self.cfg.model,
            "temperature": temperature,
        })
        text = response or self._default
        # Rough token estimate (4 chars/token)
        tokens_in = sum(len(str(m)) for m in messages) // 4
        tokens_out = len(text) // 4
        return LLMResponse(
            content=text,
            provider=self.provider_id,
            model=model or self.cfg.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason="stop",
            raw={"mock": True},
        )

    async def stream(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        text = self._default
        chunk_size = 16
        for i in range(0, len(text), chunk_size):
            yield StreamChunk(
                delta=text[i:i + chunk_size],
                provider=self.provider_id,
                model=model or self.cfg.model,
            )
        yield StreamChunk(
            delta="",
            provider=self.provider_id,
            model=model or self.cfg.model,
            finish_reason="stop",
        )
