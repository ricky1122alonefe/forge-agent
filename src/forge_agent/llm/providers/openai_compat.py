"""OpenAI-compatible client (works for DeepSeek, Moonshot, Doubao, Qwen, etc.).

Uses the standard `openai` SDK if installed; otherwise falls back to raw httpx.
Most modern Chinese LLM providers expose an OpenAI-compatible endpoint, so this
single class covers ~90% of the ecosystem.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.exceptions import (
    LLMAuthError,
    LLMContextOverflowError,
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


class OpenAICompatibleClient(LLMClient):
    """OpenAI-protocol client. Works for any provider speaking the chat
    completions API: DeepSeek, Moonshot, Doubao, Qwen, Zhipu, Baichuan, etc.
    """

    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg
        self._key_manager = APIKeyManager()
        self._api_key: str | None = None
        self._client: Any = None  # openai.AsyncOpenAI

    @property
    def provider_id(self) -> str:
        return self.cfg.provider_id

    def _resolve_key(self) -> str:
        if self._api_key:
            return self._api_key
        if hasattr(self, "_explicit_api_key") and self._explicit_api_key:
            self._api_key = self._explicit_api_key
            return self._api_key
        envs = [self.cfg.api_key_env] if self.cfg.api_key_env else []
        envs.extend(self.cfg.alt_envs)
        if not envs:
            raise LLMAuthError(
                f"No api_key_env configured for provider {self.provider_id!r}",
                provider=self.provider_id,
                hint=f"请在配置中为 provider {self.provider_id!r} 指定 api_key_env。",
            )
        resolved = self._key_manager.resolve(
            envs[0], alt_names=envs[1:], search_paths=[os.getcwd()]
        )
        if not resolved:
            primary_env = envs[0]
            raise LLMAuthError(
                f"API key for {self.provider_id!r} not found. Tried: {envs}",
                provider=self.provider_id,
                hint=f"请设置环境变量 {primary_env}，例如：export {primary_env}=your_key",
            )
        self._api_key = resolved.value
        return self._api_key

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise LLMError(
                "openai SDK not installed. Run: pip install openai",
                provider=self.provider_id,
            ) from exc
        self._client = AsyncOpenAI(
            api_key=self._resolve_key(),
            base_url=self.cfg.base_url,
            **(self.cfg.extra or {}),
        )
        return self._client

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        msgs = self._normalize(messages)
        client = self._get_client()
        try:
            resp = await client.chat.completions.create(
                model=model or self.cfg.model,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as exc:
            raise self._classify_error(exc) from exc

        return self._parse_response(resp)

    async def stream(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        msgs = self._normalize(messages)
        client = self._get_client()
        try:
            stream = await client.chat.completions.create(
                model=model or self.cfg.model,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
        except Exception as exc:
            raise self._classify_error(exc) from exc

        async for event in stream:
            try:
                choice = event.choices[0]
                delta = choice.delta.content or ""
                yield StreamChunk(
                    delta=delta,
                    provider=self.provider_id,
                    model=model or self.cfg.model,
                    finish_reason=choice.finish_reason,
                    raw=event.model_dump() if hasattr(event, "model_dump") else {},
                )
            except (AttributeError, IndexError):
                continue

    # ------------------------------------------------------------------ helpers

    def _normalize(self, messages: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if isinstance(m, ChatMessage):
                d = m.to_dict()
                out.append({k: v for k, v in d.items() if v is not None})
            elif isinstance(m, dict):
                out.append(m)
            else:
                raise TypeError(f"Unsupported message type: {type(m)}")
        return out

    def _parse_response(self, resp: Any) -> LLMResponse:
        try:
            choice = resp.choices[0]
            content = choice.message.content or ""
            usage = getattr(resp, "usage", None)
            tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
            tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
            finish_reason = getattr(choice, "finish_reason", "stop") or "stop"
        except (AttributeError, IndexError) as exc:
            raise LLMError(
                f"Unexpected response shape from {self.provider_id}: {exc}",
                provider=self.provider_id,
            ) from exc

        raw: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            raw = resp.model_dump() if hasattr(resp, "model_dump") else {}

        return LLMResponse(
            content=content,
            provider=self.provider_id,
            model=getattr(resp, "model", self.cfg.model),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            raw=raw,
        )

    def _classify_error(self, exc: Exception) -> LLMError:
        """Best-effort error classification."""
        msg = str(exc).lower()
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status == 401 or "auth" in msg or "api key" in msg or "invalid_api_key" in msg:
            return LLMAuthError(str(exc), provider=self.provider_id)
        if status == 429 or "rate" in msg or "quota" in msg:
            return LLMRateLimitError(str(exc), provider=self.provider_id)
        if status == 413 or "context_length" in msg or "too long" in msg:
            return LLMContextOverflowError(str(exc), provider=self.provider_id)
        if status and 500 <= int(status) < 600:
            return LLMNetworkError(str(exc), provider=self.provider_id)
        return LLMError(str(exc), provider=self.provider_id)
