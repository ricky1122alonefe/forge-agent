"""Core types: ChatMessage, LLMResponse, StreamChunk, LLMClient protocol.

The Protocol is deliberately tiny — implementers only need chat() and stream().
All high-level helpers (chat, multi_chat, stream) are built on top.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ Messages


@dataclass
class ChatMessage:
    """A single message in a chat conversation.

    Attributes:
        role: 'system' | 'user' | 'assistant' | 'tool'
        content: The text content.
        name: Optional speaker name (for multi-agent scenarios).
        tool_call_id: For tool responses.
        tool_calls: For assistant messages that invoke tools.
    """

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name is not None:
            d["name"] = self.name
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        return d

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> ChatMessage:
        return cls(role="assistant", content=content)


# ------------------------------------------------------------------ Response


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""

    content: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> ChatMessage:
        return ChatMessage.assistant(self.content)


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""

    delta: str
    provider: str
    model: str
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ Protocol


@runtime_checkable
class LLMClient(Protocol):
    """The interface every provider must implement."""

    @property
    def provider_id(self) -> str: ...

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]: ...


# ------------------------------------------------------------------ High-level

_DEFAULT_REGISTRY = None


def _get_default_registry():  # type: ignore[no-untyped-def]
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        from forge_agent.llm.registry import LLMRegistry

        _DEFAULT_REGISTRY = LLMRegistry()
    return _DEFAULT_REGISTRY


async def chat(
    messages: str | list[ChatMessage] | list[dict[str, str]],
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """One-shot chat. The most common entry point.

    Args:
        messages: Either a single string (treated as user message), a list of
            ChatMessage, or a list of OpenAI-style dicts.
        provider: Provider ID (e.g. "deepseek"). Defaults to config's primary.
        model: Model name. Defaults to provider's default.
        temperature: 0.0-1.0.
        max_tokens: Cap on output tokens.
        **kwargs: Provider-specific options.
            agent_id: Optional agent ID for token tracking.
            session_id: Optional session ID for token tracking.

    Returns:
        LLMResponse with content + metadata.
    """
    msgs = _normalize_messages(messages)
    registry = _get_default_registry()
    client = await registry.get_client(provider_id=provider)
    # Extract tracking kwargs (not passed to provider)
    agent_id = kwargs.pop("agent_id", None)
    session_id = kwargs.pop("session_id", None)
    t0 = time.perf_counter()
    response = await client.chat(
        msgs,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    response.latency_ms = (time.perf_counter() - t0) * 1000
    # Auto-record token usage
    _record_usage(response, agent_id=agent_id, session_id=session_id)
    return response


async def multi_chat(
    messages: str | list[ChatMessage] | list[dict[str, str]],
    *,
    providers: list[str],
    **kwargs: Any,
) -> list[LLMResponse]:
    """Send the same prompt to multiple providers concurrently.

    Returns a list of LLMResponse, one per provider. Failures are returned
    as LLMResponse with empty content and error in raw (doesn't raise).
    """
    msgs = _normalize_messages(messages)
    registry = _get_default_registry()
    clients = await asyncio.gather(*[registry.get_client(pid) for pid in providers])
    # Extract tracking kwargs
    agent_id = kwargs.pop("agent_id", None)
    session_id = kwargs.pop("session_id", None)

    async def _one(client, provider_id):  # type: ignore[no-untyped-def]
        try:
            t0 = time.perf_counter()
            r = await client.chat(msgs, **{k: v for k, v in kwargs.items() if k != "provider"})
            r.latency_ms = (time.perf_counter() - t0) * 1000
            _record_usage(r, agent_id=agent_id, session_id=session_id)
            return r
        except Exception as exc:
            log.warning("multi_chat: %s failed: %s", provider_id, exc)
            return LLMResponse(
                content="",
                provider=provider_id,
                model=kwargs.get("model", ""),
                raw={"error": str(exc)},
            )

    return await asyncio.gather(*[_one(c, p) for c, p in zip(clients, providers, strict=False)])


async def stream(
    messages: str | list[ChatMessage] | list[dict[str, str]],
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> AsyncIterator[StreamChunk]:
    """Streaming chat. Yields StreamChunk objects."""
    msgs = _normalize_messages(messages)
    registry = _get_default_registry()
    client = await registry.get_client(provider_id=provider)
    async for chunk in client.stream(
        msgs,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    ):
        yield chunk


def _normalize_messages(  # type: ignore[no-untyped-def]
    messages: str | list[ChatMessage] | list[dict[str, str]],
) -> list[dict[str, str]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    out: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, ChatMessage):
            d = m.to_dict()
            # Strip None values for clean OpenAI-compatible payload
            out.append({k: v for k, v in d.items() if v is not None})
        elif isinstance(m, dict):
            out.append(m)
        else:
            raise TypeError(f"Unsupported message type: {type(m)}")
    return out


def _record_usage(
    response: LLMResponse,
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Auto-record token usage after an LLM call. Best-effort, never raises."""
    try:
        from forge_agent.llm.tracker import get_tracker

        tracker = get_tracker()
        if tracker.enabled:
            tracker.record(response, agent_id=agent_id, session_id=session_id)
    except Exception:
        log.debug("Token tracking skipped: tracker not available")
