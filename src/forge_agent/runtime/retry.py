"""Retry policy for failed TaskRuns.

Computes the delay before the next retry attempt using exponential backoff
with optional jitter. Whether to retry at all is decided by
``TaskRun.can_retry()`` combined with the error category (non-retryable
errors short-circuit regardless of remaining attempts).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential-backoff retry policy.

    Attributes:
        max_attempts:  Max retry attempts (not counting the initial run).
        base_delay:    Base delay in seconds (doubled each attempt).
        max_delay:     Cap on the computed delay.
        jitter:        +/- fraction of delay to randomize (avoids thundering herd).
    """

    max_attempts: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0
    jitter: float = 0.1

    def delay_for(self, attempt: int) -> float:
        """Delay (seconds) before the *attempt*-th retry (1-indexed)."""
        if attempt < 1:
            return 0.0
        delay = self.base_delay * (2 ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter > 0:
            spread = delay * self.jitter
            delay += random.uniform(-spread, spread)
        return max(0.0, delay)

    def should_retry(self, attempt: int) -> bool:
        """Whether another retry is allowed after ``attempt`` retries."""
        return attempt < self.max_attempts
