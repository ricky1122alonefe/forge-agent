"""forge_agent.llm — unified LLM client for all providers.

**Design principles:**

1.  **100% local** — no key storage, no network beyond what the user calls.
2.  **Multi-provider** — DeepSeek / OpenAI / Anthropic / Ollama / etc. behind
    one Protocol.
3.  **Multi-source API keys** — explicit > env > .env > local_secrets > keyring.
4.  **User-owned configuration** — `llm_providers.json` is project-local,
    never auto-uploaded, never read by forge-agent at runtime unless asked.

**Usage (most common):**::

    from forge_agent.llm import chat

    response = await chat("Hello")
    print(response.content, response.provider, response.tokens_in)

**Multi-model voting (for the Generator's retry loop):**::

    from forge_agent.llm import multi_chat

    results = await multi_chat(
        "Write a fast Python quicksort",
        providers=["deepseek", "ollama", "claude"],
    )

**Streaming:**::

    from forge_agent.llm import stream

    async for chunk in stream("Tell me a story"):
        print(chunk.delta, end="", flush=True)
"""

from __future__ import annotations

from forge_agent.llm.config import LLMConfig, ProviderConfig, load_config
from forge_agent.llm.exceptions import (
    LLMAuthError,
    LLMContextOverflowError,
    LLMError,
    LLMNetworkError,
    LLMRateLimitError,
)
from forge_agent.llm.factory import LLMFactory, get_client, list_providers
from forge_agent.llm.protocol import (
    ChatMessage,
    LLMClient,
    LLMResponse,
    StreamChunk,
    chat,
    multi_chat,
    stream,
)
from forge_agent.llm.protocol_types import LLMChatFn, LLMStreamFn
from forge_agent.llm.registry import LLMRegistry
from forge_agent.llm.registry import get_registry as get_llm_registry
from forge_agent.llm.secrets import APIKeyManager, APIKeySource
from forge_agent.llm.tracker import TokenTracker, estimate_cost, get_tracker
from forge_agent.llm.usage_store import SQLiteUsageStore, TokenUsage

__all__ = [
    # Secrets
    "APIKeyManager",
    "APIKeySource",
    # Core types
    "ChatMessage",
    "LLMAuthError",
    # Protocol types
    "LLMChatFn",
    "LLMClient",
    # Config
    "LLMConfig",
    "LLMContextOverflowError",
    # Exceptions
    "LLMError",
    # Factory
    "LLMFactory",
    "LLMNetworkError",
    "LLMRateLimitError",
    # Registry
    "LLMRegistry",
    "LLMResponse",
    "LLMStreamFn",
    "ProviderConfig",
    "SQLiteUsageStore",
    "StreamChunk",
    # Token tracking
    "TokenTracker",
    "TokenUsage",
    # High-level helpers
    "chat",
    "estimate_cost",
    "get_client",
    "get_llm_registry",
    "get_tracker",
    "list_providers",
    "load_config",
    "multi_chat",
    "stream",
]
