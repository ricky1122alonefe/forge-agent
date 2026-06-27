"""LLMRegistry — manages configured LLM clients.

Mirrors the design of AgentRegistry: lazy creation, caching, list by criteria.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from forge_agent.llm.config import LLMConfig, ProviderConfig, load_config
from forge_agent.llm.protocol import LLMClient

log = logging.getLogger(__name__)


class LLMRegistry:
    """Manages LLM clients keyed by provider_id."""

    _instance: "LLMRegistry | None" = None

    def __new__(cls) -> "LLMRegistry":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._initialized = False
            cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._config: LLMConfig | None = None
        self._clients: dict[str, LLMClient] = {}
        self._lock = asyncio.Lock()
        self._initialized = True

    # ------------------------------------------------------------------ Config

    def configure(self, config: LLMConfig) -> None:
        """Replace the current config (does NOT invalidate existing clients)."""
        self._config = config
        log.info("LLMRegistry configured with %d providers", len(config.providers))

    def reload(self, **kwargs: Any) -> None:
        """Re-load config from disk."""
        self.configure(load_config(**kwargs))
        self._clients.clear()

    @property
    def config(self) -> LLMConfig:
        if self._config is None:
            self._config = load_config()
        return self._config

    # ------------------------------------------------------------------ Clients

    async def get_client(
        self,
        provider_id: str | None = None,
        *,
        force_new: bool = False,
    ) -> LLMClient:
        """Get (or create) a client for the given provider_id.

        Defaults to config.primary_id.
        """
        pid = provider_id or self.config.primary_id
        if not force_new and pid in self._clients:
            return self._clients[pid]
        async with self._lock:
            if not force_new and pid in self._clients:
                return self._clients[pid]
            provider_cfg = self.config.providers.get(pid)
            if provider_cfg is None:
                from forge_agent.exceptions import ProviderNotConfiguredError
                raise ProviderNotConfiguredError(pid, available=list(self.config.providers.keys()))
            if not provider_cfg.enabled:
                log.warning("Provider %s is disabled in config", pid)
            client = self._build_client(provider_cfg)
            self._clients[pid] = client
            return client

    def _build_client(self, cfg: ProviderConfig) -> LLMClient:
        """Instantiate the right provider implementation."""
        from forge_agent.llm.providers import build_client
        return build_client(cfg)

    # ------------------------------------------------------------------ Query

    def list_providers(self) -> list[str]:
        return list(self.config.providers.keys())

    def list_enabled(self) -> list[str]:
        return [p.provider_id for p in self.config.get_enabled()]

    def has(self, provider_id: str) -> bool:
        return provider_id in self.config.providers

    async def shutdown(self) -> None:
        self._clients.clear()
        log.info("LLMRegistry shut down")


def get_registry() -> LLMRegistry:
    return LLMRegistry()
