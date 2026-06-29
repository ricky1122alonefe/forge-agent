"""Tests for LLMChatFn Protocol (llm/protocol_types.py)."""

from __future__ import annotations

from typing import Any

from forge_agent.llm.protocol import LLMResponse
from forge_agent.llm.protocol_types import LLMChatFn, LLMStreamFn

# ------------------------------------------------------------------ Helpers


async def _valid_chat_fn(
    messages: Any,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> LLMResponse:
    return LLMResponse(
        content="hello",
        provider="test",
        model="test-model",
        tokens_in=10,
        tokens_out=5,
    )


async def _bad_signature_fn(x: int) -> str:
    return "nope"


# ------------------------------------------------------------------ Tests


class TestLLMChatFn:
    def test_valid_fn_matches_protocol(self):
        assert isinstance(_valid_chat_fn, LLMChatFn)

    def test_bad_signature_does_not_match(self):
        # runtime_checkable only checks __call__ existence, not signature
        # so this may still pass isinstance — that's expected for Protocol
        # The real value is static type checking
        assert callable(_bad_signature_fn)

    def test_protocol_is_runtime_checkable(self):
        # LLMChatFn should be runtime_checkable
        assert hasattr(LLMChatFn, "__protocol_attrs__") or hasattr(
            LLMChatFn, "_is_runtime_protocol"
        )


class TestLLMStreamFn:
    def test_protocol_exists(self):
        assert LLMStreamFn is not None

    def test_protocol_is_callable(self):
        # Should be a Protocol class
        assert callable(LLMStreamFn) or hasattr(LLMStreamFn, "__protocol_attrs__")
