"""Tests for the retry and rollback mechanism (T1.5).

Covers:
- Successful execution (no retry)
- Retry on retryable errors
- Immediate failure on non-retryable errors
- Exponential backoff timing
- Retry logging
- Rollback to previous stable version
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from forge_agent.generator.retry import (
    AttemptRecord,
    NonRetryableError,
    RetryableError,
    RetryConfig,
    RetryManager,
    RollbackManager,
    classify_error,
)

# ------------------------------------------------------------------ Error classifier


def test_classify_timeout_as_retryable() -> None:
    """Timeout errors should be retryable."""
    error = classify_error("Connection timeout after 30s")
    assert isinstance(error, RetryableError)
    assert error == RetryableError.NETWORK_TIMEOUT


def test_classify_rate_limit_as_retryable() -> None:
    """Rate limit errors should be retryable."""
    error = classify_error("Rate limit exceeded (429)")
    assert isinstance(error, RetryableError)
    assert error == RetryableError.RATE_LIMIT


def test_classify_syntax_error_as_non_retryable() -> None:
    """Syntax errors should NOT be retryable."""
    error = classify_error("SyntaxError: invalid syntax")
    assert isinstance(error, NonRetryableError)
    assert error == NonRetryableError.SYNTAX_ERROR


def test_classify_forbidden_import_as_non_retryable() -> None:
    """Forbidden import errors should NOT be retryable."""
    error = classify_error("forbidden import: subprocess")
    assert isinstance(error, NonRetryableError)
    assert error == NonRetryableError.FORBIDDEN_IMPORT


def test_classify_validation_failed_as_retryable() -> None:
    """Validation failures should be retryable (LLM might fix on retry)."""
    error = classify_error("validation failed: missing type hints")
    assert isinstance(error, RetryableError)
    assert error == RetryableError.VALIDATION_FAILED


def test_classify_exception_object() -> None:
    """Should work with Exception objects, not just strings."""
    error = classify_error(TimeoutError("Connection timed out"))
    assert isinstance(error, RetryableError)


# ------------------------------------------------------------------ Retry manager: success


@pytest.mark.asyncio
async def test_retry_success_first_attempt() -> None:
    """Should succeed on first attempt without retry."""
    manager = RetryManager()

    async def success_func():
        return "result"

    result, retry_log = await manager.execute_with_retry(success_func)

    assert result == "result"
    assert len(retry_log) == 1
    assert retry_log[0].attempt == 1
    assert retry_log[0].success is True


@pytest.mark.asyncio
async def test_retry_success_second_attempt() -> None:
    """Should retry once and succeed."""
    manager = RetryManager(RetryConfig(max_attempts=3, initial_delay=0.01))

    call_count = 0

    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("Connection timeout")
        return "result"

    result, retry_log = await manager.execute_with_retry(flaky_func)

    assert result == "result"
    assert call_count == 2
    assert len(retry_log) == 2
    assert retry_log[0].success is False
    assert retry_log[0].error_type == "network_timeout"
    assert retry_log[1].success is True


@pytest.mark.asyncio
async def test_retry_success_third_attempt() -> None:
    """Should retry twice and succeed on third attempt."""
    manager = RetryManager(RetryConfig(max_attempts=3, initial_delay=0.01))

    call_count = 0

    async def very_flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Rate limit exceeded (429)")
        return "result"

    result, retry_log = await manager.execute_with_retry(very_flaky_func)

    assert result == "result"
    assert call_count == 3
    assert len(retry_log) == 3
    assert retry_log[0].success is False
    assert retry_log[1].success is False
    assert retry_log[2].success is True


# ------------------------------------------------------------------ Retry manager: failure


@pytest.mark.asyncio
async def test_retry_exhausted() -> None:
    """Should raise after all retries exhausted."""
    manager = RetryManager(RetryConfig(max_attempts=3, initial_delay=0.01))

    async def always_fail():
        raise TimeoutError("Connection timeout")

    with pytest.raises(TimeoutError, match="Connection timeout"):
        await manager.execute_with_retry(always_fail)


@pytest.mark.asyncio
async def test_retry_non_retryable_error() -> None:
    """Should NOT retry on non-retryable errors."""
    manager = RetryManager(RetryConfig(max_attempts=3, initial_delay=0.01))

    call_count = 0

    async def syntax_error_func():
        nonlocal call_count
        call_count += 1
        raise SyntaxError("invalid syntax")

    with pytest.raises(SyntaxError):
        await manager.execute_with_retry(syntax_error_func)

    # Should only be called once (no retry)
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_forbidden_import_no_retry() -> None:
    """Should NOT retry on forbidden import errors."""
    manager = RetryManager(RetryConfig(max_attempts=3, initial_delay=0.01))

    call_count = 0

    async def forbidden_import_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("forbidden import: subprocess")

    with pytest.raises(ValueError, match="forbidden import"):
        await manager.execute_with_retry(forbidden_import_func)

    assert call_count == 1


# ------------------------------------------------------------------ Exponential backoff


@pytest.mark.asyncio
async def test_exponential_backoff_timing() -> None:
    """Should apply exponential backoff between retries."""
    config = RetryConfig(
        max_attempts=3,
        initial_delay=0.1,
        backoff_factor=2.0,
    )
    manager = RetryManager(config)

    timestamps: list[float] = []

    async def timed_func():
        timestamps.append(asyncio.get_event_loop().time())
        if len(timestamps) < 3:
            raise TimeoutError("timeout")
        return "result"

    await manager.execute_with_retry(timed_func)

    # Check delays: ~0.1s, ~0.2s
    assert len(timestamps) == 3
    delay1 = timestamps[1] - timestamps[0]
    delay2 = timestamps[2] - timestamps[1]

    # Allow 20% tolerance
    assert 0.08 <= delay1 <= 0.12, f"First delay {delay1:.3f}s not ~0.1s"
    assert 0.16 <= delay2 <= 0.24, f"Second delay {delay2:.3f}s not ~0.2s"


# ------------------------------------------------------------------ Retry logging


@pytest.mark.asyncio
async def test_retry_log_records_all_attempts() -> None:
    """Should record all attempts in retry log."""
    manager = RetryManager(RetryConfig(max_attempts=3, initial_delay=0.01))

    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Rate limit (429)")
        return "result"

    result, retry_log = await manager.execute_with_retry(func)

    assert result == "result"
    assert len(retry_log) == 3

    # First attempt
    assert retry_log[0].attempt == 1
    assert retry_log[0].success is False
    assert retry_log[0].error_type == "rate_limit"
    assert "429" in retry_log[0].error_message

    # Second attempt
    assert retry_log[1].attempt == 2
    assert retry_log[1].success is False

    # Third attempt (success)
    assert retry_log[2].attempt == 3
    assert retry_log[2].success is True
    assert retry_log[2].error_type is None


@pytest.mark.asyncio
async def test_retry_log_duration() -> None:
    """Should record duration for each attempt."""
    manager = RetryManager(RetryConfig(max_attempts=2, initial_delay=0.01))

    async def slow_func():
        await asyncio.sleep(0.05)
        return "result"

    result, retry_log = await manager.execute_with_retry(slow_func)

    assert result == "result"
    assert len(retry_log) == 1
    assert retry_log[0].duration_ms >= 50  # At least 50ms


# ------------------------------------------------------------------ Rollback manager


def test_rollback_to_previous_version() -> None:
    """Should rollback to the previous stable version."""
    # Mock code store
    mock_store = MagicMock()
    mock_manifest = MagicMock()
    mock_entry = MagicMock()

    # Setup versions: v1 (passed), v2 (failed), v3 (current, failed)
    v1 = MagicMock(version="v1", validation_status="passed")
    v2 = MagicMock(version="v2", validation_status="failed")
    v3 = MagicMock(version="v3", validation_status="failed")

    mock_entry.versions = [v1, v2, v3]
    mock_manifest.agents = {"test.agent": mock_entry}
    mock_store.manifest = mock_manifest

    # Mock load to return a SavedCode-like object
    mock_saved = MagicMock(version="v1")
    mock_store.load.return_value = mock_saved

    # Test rollback
    rollback_mgr = RollbackManager(mock_store)
    result = rollback_mgr.rollback("test.agent")

    assert result is not None
    assert result.version == "v1"
    mock_store.load.assert_called_once_with("test.agent", "v1")


def test_rollback_no_previous_version() -> None:
    """Should return None if no previous version exists."""
    mock_store = MagicMock()
    mock_manifest = MagicMock()
    mock_entry = MagicMock()

    # Only one version
    v1 = MagicMock(version="v1", validation_status="passed")
    mock_entry.versions = [v1]
    mock_manifest.agents = {"test.agent": mock_entry}
    mock_store.manifest = mock_manifest

    rollback_mgr = RollbackManager(mock_store)
    result = rollback_mgr.rollback("test.agent")

    assert result is None


def test_rollback_no_stable_version() -> None:
    """Should return None if no stable version exists."""
    mock_store = MagicMock()
    mock_manifest = MagicMock()
    mock_entry = MagicMock()

    # All versions failed
    v1 = MagicMock(version="v1", validation_status="failed")
    v2 = MagicMock(version="v2", validation_status="failed")
    mock_entry.versions = [v1, v2]
    mock_manifest.agents = {"test.agent": mock_entry}
    mock_store.manifest = mock_manifest

    rollback_mgr = RollbackManager(mock_store)
    result = rollback_mgr.rollback("test.agent")

    assert result is None


def test_rollback_agent_not_found() -> None:
    """Should return None if agent doesn't exist."""
    mock_store = MagicMock()
    mock_manifest = MagicMock()
    mock_manifest.agents = {}
    mock_store.manifest = mock_manifest

    rollback_mgr = RollbackManager(mock_store)
    result = rollback_mgr.rollback("nonexistent.agent")

    assert result is None


def test_get_stable_versions() -> None:
    """Should return list of all stable versions."""
    mock_store = MagicMock()
    mock_manifest = MagicMock()
    mock_entry = MagicMock()

    v1 = MagicMock(version="v1", validation_status="passed")
    v2 = MagicMock(version="v2", validation_status="failed")
    v3 = MagicMock(version="v3", validation_status="passed")
    v4 = MagicMock(version="v4", validation_status="passed")

    mock_entry.versions = [v1, v2, v3, v4]
    mock_manifest.agents = {"test.agent": mock_entry}
    mock_store.manifest = mock_manifest

    rollback_mgr = RollbackManager(mock_store)
    stable = rollback_mgr.get_stable_versions("test.agent")

    assert stable == ["v1", "v3", "v4"]


# ------------------------------------------------------------------ AttemptRecord


def test_attempt_record_dataclass() -> None:
    """AttemptRecord should be a proper dataclass."""
    record = AttemptRecord(
        attempt=1,
        success=True,
        duration_ms=123.45,
    )

    assert record.attempt == 1
    assert record.success is True
    assert record.duration_ms == 123.45
    assert record.error_type is None
    assert record.error_message is None
    assert record.timestamp > 0


# ------------------------------------------------------------------ RetryConfig


def test_retry_config_defaults() -> None:
    """RetryConfig should have sensible defaults."""
    config = RetryConfig()

    assert config.max_attempts == 3
    assert config.backoff_factor == 1.5
    assert config.initial_delay == 1.0
    assert RetryableError.NETWORK_TIMEOUT in config.retryable_errors
    assert RetryableError.RATE_LIMIT in config.retryable_errors


def test_retry_config_custom() -> None:
    """RetryConfig should accept custom values."""
    config = RetryConfig(
        max_attempts=5,
        backoff_factor=2.0,
        initial_delay=0.5,
        retryable_errors={RetryableError.NETWORK_TIMEOUT},
    )

    assert config.max_attempts == 5
    assert config.backoff_factor == 2.0
    assert config.initial_delay == 0.5
    assert len(config.retryable_errors) == 1
