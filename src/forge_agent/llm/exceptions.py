"""Exception types for the LLM layer.

Categorizing errors is important because the Generator uses them to decide
retry strategy:
    - LLMAuthError           → permanent (don't retry, tell user to fix key)
    - LLMRateLimitError      → transient (retry with backoff)
    - LLMNetworkError        → transient (retry)
    - LLMContextOverflowError → permanent (need to shrink prompt)
    - LLMError (base)        → unknown

All LLM errors inherit from :class:`forge_agent.exceptions.LLMError` so that
the CLI/TUI can present a unified, friendly Chinese message.
"""

from __future__ import annotations

from forge_agent.exceptions import LLMError as ForgeLLMError


class LLMError(ForgeLLMError):
    """Base class for all LLM-related errors."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, provider=provider, model=model, hint=hint)


class LLMAuthError(LLMError):
    """401/403 — bad API key. Generator should NOT auto-retry."""

    default_hint = "请检查 API Key 是否正确设置。"


class LLMRateLimitError(LLMError):
    """429 — too many requests. Generator SHOULD retry with backoff."""

    default_hint = "请求过于频繁，请稍后重试或降低调用频率。"


class LLMNetworkError(LLMError):
    """Connection timeout / DNS / 5xx. Generator SHOULD retry."""

    default_hint = "网络连接异常，请检查网络或稍后重试。"


class LLMContextOverflowError(LLMError):
    """413 / context_length_exceeded. Generator should NOT retry, must shrink."""

    default_hint = "上下文超出模型限制，请缩短 prompt 或减少历史消息。"


class LLMConfigError(LLMError):
    """Configuration problem (missing key, bad model name, etc.)."""

    default_hint = "LLM 配置有误，请使用 `forge-agent llm show` 检查当前配置。"
