"""LLMChatFn Protocol — type-safe callable signature for LLM chat functions.

Replaces `llm_chat: Any` with a proper Protocol so callers know the
expected signature and type checkers can verify correctness.

Usage::

    from forge_agent.llm.protocol_types import LLMChatFn

    class CodeGenerator:
        def __init__(self, llm_chat: LLMChatFn):
            self.llm_chat = llm_chat
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from forge_agent.llm.protocol import LLMResponse


@runtime_checkable
class LLMChatFn(Protocol):
    """Protocol for an async LLM chat callable.

    Matches the signature of `forge_agent.llm.chat()`.
    """

    async def __call__(
        self,
        messages: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...


@runtime_checkable
class LLMStreamFn(Protocol):
    """Protocol for an async LLM streaming callable."""

    async def __call__(
        self,
        messages: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Any: ...
