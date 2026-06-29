"""Retry and rollback mechanism for the generation pipeline (T1.5).

Provides intelligent retry with:
- Error classification (retryable vs non-retryable)
- Exponential backoff
- Rollback to previous stable version on total failure
- Detailed retry logging

Usage::

    from forge_agent.generator.retry import RetryManager, RetryConfig

    config = RetryConfig(max_attempts=3, backoff_factor=1.5)
    manager = RetryManager(config)

    result, retry_log = await manager.execute_with_retry(
        generate_func, requirement="monitor stock prices"
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ Error types


class RetryableError(str, Enum):
    """Errors that can be retried."""

    NETWORK_TIMEOUT = "network_timeout"
    RATE_LIMIT = "rate_limit"
    LLM_OVERLOAD = "llm_overload"
    VALIDATION_FAILED = "validation_failed"
    SANDBOX_TIMEOUT = "sandbox_timeout"
    SANDBOX_ERROR = "sandbox_error"
    GENERATION_FAILED = "generation_failed"


class NonRetryableError(str, Enum):
    """Errors that should NOT be retried."""

    SYNTAX_ERROR = "syntax_error"
    PERMISSION_DENIED = "permission_denied"
    INVALID_CONFIG = "invalid_config"
    FORBIDDEN_IMPORT = "forbidden_import"
    INVALID_REQUIREMENT = "invalid_requirement"


# ------------------------------------------------------------------ Config


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    backoff_factor: float = 1.5
    initial_delay: float = 1.0
    retryable_errors: set[RetryableError] = field(
        default_factory=lambda: {
            RetryableError.NETWORK_TIMEOUT,
            RetryableError.RATE_LIMIT,
            RetryableError.LLM_OVERLOAD,
            RetryableError.VALIDATION_FAILED,
            RetryableError.SANDBOX_TIMEOUT,
            RetryableError.SANDBOX_ERROR,
            RetryableError.GENERATION_FAILED,
        }
    )


# ------------------------------------------------------------------ Error classifier


def classify_error(error: Exception | str) -> RetryableError | NonRetryableError:
    """Classify an error as retryable or non-retryable.

    Args:
        error: Exception instance or error message string.

    Returns:
        Classified error type.
    """
    error_str = str(error).lower()
    error_type_name = type(error).__name__ if isinstance(error, Exception) else ""

    # Non-retryable errors (check first — more specific)
    if (
        "syntax error" in error_str
        or "syntaxerror" in error_str
        or "invalid syntax" in error_str
        or error_type_name == "SyntaxError"
    ):
        return NonRetryableError.SYNTAX_ERROR
    if "forbidden import" in error_str or "forbidden_import" in error_str:
        return NonRetryableError.FORBIDDEN_IMPORT
    if "permission denied" in error_str or "permissionerror" in error_str:
        return NonRetryableError.PERMISSION_DENIED
    if "invalid config" in error_str or "invalid_config" in error_str:
        return NonRetryableError.INVALID_CONFIG
    if "invalid requirement" in error_str or "empty requirement" in error_str:
        return NonRetryableError.INVALID_REQUIREMENT

    # Retryable errors
    if "timeout" in error_str or "timed out" in error_str:
        return RetryableError.NETWORK_TIMEOUT
    if "rate limit" in error_str or "429" in error_str or "too many requests" in error_str:
        return RetryableError.RATE_LIMIT
    if "overloaded" in error_str or "503" in error_str or "service unavailable" in error_str:
        return RetryableError.LLM_OVERLOAD
    if "validation" in error_str and "failed" in error_str:
        return RetryableError.VALIDATION_FAILED
    if "sandbox" in error_str and "timeout" in error_str:
        return RetryableError.SANDBOX_TIMEOUT
    if "sandbox" in error_str:
        return RetryableError.SANDBOX_ERROR
    if "generation" in error_str and "failed" in error_str:
        return RetryableError.GENERATION_FAILED

    # Default: retryable (optimistic)
    return RetryableError.GENERATION_FAILED


# ------------------------------------------------------------------ Retry manager


@dataclass
class AttemptRecord:
    """Record of a single retry attempt."""

    attempt: int
    success: bool
    error_type: str | None = None
    error_message: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class RetryManager:
    """Manages retry logic with exponential backoff.

    Usage::

        manager = RetryManager()
        result, log = await manager.execute_with_retry(my_func, arg1, arg2)
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, list[AttemptRecord]]:
        """Execute function with retry logic.

        Args:
            func: Async function to execute.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Tuple of (result, retry_log) where retry_log is a list of
            AttemptRecord for each attempt.

        Raises:
            Exception: If all retries exhausted or non-retryable error.
        """
        retry_log: list[AttemptRecord] = []
        last_error: Exception | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            t0 = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - t0) * 1000

                retry_log.append(
                    AttemptRecord(
                        attempt=attempt,
                        success=True,
                        duration_ms=duration_ms,
                    )
                )

                if attempt > 1:
                    log.info(
                        "Retry succeeded on attempt %d/%d (%.1fms)",
                        attempt,
                        self.config.max_attempts,
                        duration_ms,
                    )

                return result, retry_log

            except Exception as exc:
                duration_ms = (time.perf_counter() - t0) * 1000
                error_type = classify_error(exc)
                error_msg = str(exc)

                retry_log.append(
                    AttemptRecord(
                        attempt=attempt,
                        success=False,
                        error_type=error_type.value,
                        error_message=error_msg,
                        duration_ms=duration_ms,
                    )
                )

                last_error = exc

                # Check if error is retryable
                if isinstance(error_type, NonRetryableError):
                    log.warning(
                        "Non-retryable error on attempt %d: %s — stopping",
                        attempt,
                        error_type.value,
                    )
                    raise

                # Check if we've exhausted retries
                if attempt >= self.config.max_attempts:
                    log.error(
                        "All %d retry attempts exhausted. Last error: %s",
                        self.config.max_attempts,
                        error_msg,
                    )
                    break

                # Exponential backoff
                delay = self.config.initial_delay * (self.config.backoff_factor ** (attempt - 1))
                log.info(
                    "Attempt %d/%d failed (%s). Retrying in %.2fs...",
                    attempt,
                    self.config.max_attempts,
                    error_type.value,
                    delay,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        assert last_error is not None
        raise last_error


# ------------------------------------------------------------------ Rollback manager


class RollbackManager:
    """Manages rollback to previous stable versions.

    Usage::

        rollback_mgr = RollbackManager(code_store)
        previous = rollback_mgr.rollback("stock.monitor")
        if previous:
            print(f"Rolled back to {previous.version}")
    """

    def __init__(self, code_store: Any) -> None:
        """Initialize with a FileCodeStore instance."""
        self.code_store = code_store

    def rollback(self, agent_id: str) -> Any | None:
        """Rollback to the previous stable version.

        Args:
            agent_id: Agent identifier (e.g. "stock.monitor").

        Returns:
            SavedCode of the previous stable version, or None if no
            stable version exists.
        """
        manifest = self.code_store.manifest
        entry = manifest.agents.get(agent_id)

        if not entry or len(entry.versions) < 2:
            log.info("No previous version to rollback for %s", agent_id)
            return None

        # Find the last stable version (skip the current one)
        for version_meta in reversed(entry.versions[:-1]):
            if version_meta.validation_status == "passed":
                log.info(
                    "Rolling back %s to version %s",
                    agent_id,
                    version_meta.version,
                )
                return self.code_store.load(agent_id, version_meta.version)

        log.warning("No stable version found for %s", agent_id)
        return None

    def get_stable_versions(self, agent_id: str) -> list[str]:
        """Get list of all stable versions for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            List of version strings (e.g. ["v1", "v2"]).
        """
        manifest = self.code_store.manifest
        entry = manifest.agents.get(agent_id)

        if not entry:
            return []

        return [v.version for v in entry.versions if v.validation_status == "passed"]
