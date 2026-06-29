"""Google Gemini client.

Gemini exposes an OpenAI-compatible chat completions endpoint, so this client
is a thin wrapper around OpenAICompatibleClient that sets the correct default
base_url and API key resolution.

Usage::

    export GEMINI_API_KEY=...
    # or pass api_key_env in ProviderConfig
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from forge_agent.llm.config import ProviderConfig
from forge_agent.llm.exceptions import LLMAuthError, LLMError
from forge_agent.llm.protocol import LLMResponse, StreamChunk
from forge_agent.llm.providers.openai_compat import OpenAICompatibleClient
from forge_agent.llm.secrets import APIKeyManager

log = logging.getLogger(__name__)


class GeminiClient(OpenAICompatibleClient):
    """Google Gemini client using the OpenAI-compatible endpoint."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(self, cfg: ProviderConfig) -> None:
        super().__init__(cfg)
        self._key_manager = APIKeyManager()
        self._explicit_api_key: str | None = None
        if cfg.api_key:
            self._explicit_api_key = cfg.api_key

    @property
    def provider_id(self) -> str:
        return self.cfg.provider_id

    def _resolve_key(self) -> str:
        if self._explicit_api_key:
            return self._explicit_api_key
        envs = [self.cfg.api_key_env] if self.cfg.api_key_env else ["GEMINI_API_KEY"]
        envs.extend(self.cfg.alt_envs)
        resolved = self._key_manager.resolve(
            envs[0], alt_names=envs[1:], search_paths=[os.getcwd()]
        )
        if not resolved:
            raise LLMAuthError(
                f"API key for {self.provider_id!r} not found. Tried: {envs}",
                provider=self.provider_id,
            )
        return resolved.value

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

        base_url = self.cfg.base_url or self.DEFAULT_BASE_URL
        self._client = AsyncOpenAI(
            api_key=self._resolve_key(),
            base_url=base_url,
            **(self.cfg.extra or {}),
        )
        return self._client

    async def chat(self, messages, **kwargs) -> LLMResponse:
        return await super().chat(messages, **kwargs)

    async def stream(self, messages, **kwargs) -> AsyncIterator[StreamChunk]:
        async for chunk in super().stream(messages, **kwargs):
            yield chunk
