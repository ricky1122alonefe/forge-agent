"""Anthropic Claude client.

Uses the official anthropic SDK if available; otherwise falls back to httpx.
The chat() method normalizes OpenAI-style messages to Anthropic format.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.exceptions import (
    LLMAuthError,
    LLMError,
    LLMNetworkError,
    LLMRateLimitError,
)
from forge_agent.llm.protocol import (
    ChatMessage,
    LLMClient,
    LLMResponse,
    StreamChunk,
)
from forge_agent.llm.secrets import APIKeyManager

log = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Anthropic Claude client. Stub for v0.2; full impl in v0.3."""

    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg
        self._key_manager = APIKeyManager()
        self._api_key: str | None = None
        self._client: Any = None

    @property
    def provider_id(self) -> str:
        return self.cfg.provider_id

    def _resolve_key(self) -> str:
        if self._api_key:
            return self._api_key
        envs = [self.cfg.api_key_env] if self.cfg.api_key_env else ["ANTHROPIC_API_KEY"]
        envs.extend(self.cfg.alt_envs)
        resolved = self._key_manager.resolve(envs[0], alt_names=envs[1:], search_paths=[os.getcwd()])
        if not resolved:
            raise LLMAuthError(
                f"API key for {self.provider_id!r} not found. Tried: {envs}",
                provider=self.provider_id,
            )
        self._api_key = resolved.value
        return self._api_key

    async def chat(self, messages, **kwargs):
        try:
            from anthropic import AsyncAnthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise LLMError(
                "anthropic SDK not installed. Run: pip install anthropic",
                provider=self.provider_id,
            ) from exc
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self._resolve_key())
        # Normalize to Anthropic format (system extracted, rest = messages)
        system = None
        msgs: list[dict[str, Any]] = []
        for m in messages:
            d = m.to_dict() if isinstance(m, ChatMessage) else m
            if d.get("role") == "system":
                system = d["content"]
            else:
                msgs.append({"role": d["role"], "content": d["content"]})
        try:
            resp = await self._client.messages.create(
                model=kwargs.get("model") or self.cfg.model,
                max_tokens=kwargs.get("max_tokens", 1024),
                system=system or "",
                messages=msgs,
                **{k: v for k, v in kwargs.items() if k not in ("model", "max_tokens")},
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "auth" in msg or "api key" in msg:
                raise LLMAuthError(str(exc), provider=self.provider_id) from exc
            if "rate" in msg:
                raise LLMRateLimitError(str(exc), provider=self.provider_id) from exc
            raise LLMError(str(exc), provider=self.provider_id) from exc

        content = ""
        for block in getattr(resp, "content", []):
            content += getattr(block, "text", "") or ""
        return LLMResponse(
            content=content,
            provider=self.provider_id,
            model=getattr(resp, "model", self.cfg.model),
            tokens_in=int(getattr(resp.usage, "input_tokens", 0) or 0),
            tokens_out=int(getattr(resp.usage, "output_tokens", 0) or 0),
            finish_reason=getattr(resp, "stop_reason", "stop") or "stop",
            raw={},
        )

    async def stream(self, messages, **kwargs) -> AsyncIterator[StreamChunk]:
        # TODO: implement streaming
        yield StreamChunk(delta="", provider=self.provider_id, model=self.cfg.model, finish_reason="error")
        return
