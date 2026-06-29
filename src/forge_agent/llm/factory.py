"""LLMFactory + high-level convenience functions.

Wraps LLMRegistry for the common case of "I just want a client".
"""

from __future__ import annotations

import logging
from typing import Any

from forge_agent.llm.config import LLMConfig, load_config
from forge_agent.llm.protocol import LLMClient
from forge_agent.llm.registry import get_registry

log = logging.getLogger(__name__)


class LLMFactory:
    """One-shot factory for ad-hoc client creation (doesn't use the registry)."""

    @staticmethod
    def create(
        provider_type: str,
        *,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> LLMClient:
        from forge_agent.llm.config import ProviderConfig
        from forge_agent.llm.providers import build_client_from_type

        cfg = ProviderConfig(
            provider_id=provider_type,
            type=provider_type,
            model=model,
            base_url=base_url,
            api_key_env=None,
            extra=kwargs,
        )
        client = build_client_from_type(cfg)
        # Inject explicit api_key if provided
        if api_key and hasattr(client, "_explicit_api_key"):
            client._explicit_api_key = api_key
        return client


async def get_client(
    provider: str | None = None,
    *,
    config: LLMConfig | None = None,
) -> LLMClient:
    """Convenience: get a client from the global registry.

    Loads config on first use.
    """
    reg = get_registry()
    if config is not None:
        reg.configure(config)
    elif reg.config is None:
        reg.configure(load_config())
    return await reg.get_client(provider)


def list_providers(*, enabled_only: bool = False) -> list[str]:
    reg = get_registry()
    if enabled_only:
        return reg.list_enabled()
    return reg.list_providers()
