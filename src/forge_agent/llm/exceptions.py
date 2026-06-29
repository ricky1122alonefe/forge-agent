"""Exception types for the LLM layer.

Categorizing errors is important because the Generator uses them to decide
retry strategy:
    - LLMAuthError           → permanent (don't retry, tell user to fix key)
    - LLMRateLimitError      → transient (retry with backoff)
    - LLMNetworkError        → transient (retry)
    - LLMContextOverflowError → permanent (need to shrink prompt)
    - LLMError (base)        → unknown
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM-related errors."""

    def __init__(
        self, message: str, *, provider: str | None = None, model: str | None = None
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.message = message


class LLMAuthError(LLMError):
    """401/403 — bad API key. Generator should NOT auto-retry."""


class LLMRateLimitError(LLMError):
    """429 — too many requests. Generator SHOULD retry with backoff."""


class LLMNetworkError(LLMError):
    """Connection timeout / DNS / 5xx. Generator SHOULD retry."""


class LLMContextOverflowError(LLMError):
    """413 / context_length_exceeded. Generator should NOT retry, must shrink."""


class LLMConfigError(LLMError):
    """Configuration problem (missing key, bad model name, etc.)."""
