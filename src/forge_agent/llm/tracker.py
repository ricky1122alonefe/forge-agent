"""TokenTracker — global token consumption tracker.

Records every LLM call with agent_id / session_id context, persists to SQLite,
and provides query + summary APIs for cost analysis.

Usage::

    from forge_agent.llm.tracker import get_tracker

    tracker = get_tracker()
    tracker.record(response, agent_id="stock.monitor", session_id="gen_abc123")

    # Query
    records = tracker.query(agent_id="stock.monitor")

    # Summary
    stats = tracker.summary(session_id="gen_abc123", group_by="provider")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from forge_agent.llm.protocol import LLMResponse
from forge_agent.llm.usage_store import SQLiteUsageStore, TokenUsage

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ Pricing

# USD per 1M tokens (input, output) — approximate as of 2026-06
MODEL_PRICING: dict[str, dict[str, float]] = {
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-coder": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Anthropic
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    # Qwen
    "qwen-turbo": {"input": 0.30, "output": 0.60},
    "qwen-plus": {"input": 0.80, "output": 2.00},
    "qwen-max": {"input": 2.00, "output": 6.00},
    # Ollama / local
    "qwen2.5:7b": {"input": 0.0, "output": 0.0},
    "llama3": {"input": 0.0, "output": 0.0},
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate cost in USD based on token counts.

    Uses MODEL_PRICING table. Returns 0.0 if model is unknown.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        # Try prefix match (e.g. "gpt-4o-2024-05-13" → "gpt-4o")
        for key, p in MODEL_PRICING.items():
            if model.startswith(key):
                pricing = p
                break
    if pricing is None:
        return 0.0
    cost = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000
    return round(cost, 8)


# ------------------------------------------------------------------ Tracker

class TokenTracker:
    """Global token consumption tracker.

    Wraps a SQLiteUsageStore and provides a clean API for recording,
    querying, and summarizing LLM token usage.
    """

    _instance: "TokenTracker | None" = None

    def __new__(cls, db_path: Path | str | None = None) -> "TokenTracker":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._store = SQLiteUsageStore(db_path)
            inst._enabled = True
            cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for tests)."""
        if cls._instance is not None:
            cls._instance._store.close()
            cls._instance = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def record(
        self,
        response: LLMResponse,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TokenUsage:
        """Record a single LLM call's token consumption.

        If the response already has cost_usd, use it.
        Otherwise, estimate from the model pricing table.
        """
        if not self._enabled:
            return TokenUsage(
                provider=response.provider,
                model=response.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost_usd=0.0,
                timestamp="",
            )

        cost = response.cost_usd
        if cost is None or cost == 0.0:
            cost = estimate_cost(response.model, response.tokens_in, response.tokens_out)

        from datetime import datetime, timezone
        usage = TokenUsage(
            provider=response.provider,
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=cost,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        try:
            return self._store.insert(usage)
        except Exception:  # noqa: BLE001
            log.exception("Failed to record token usage")
            return usage

    def query(
        self,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        provider: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[TokenUsage]:
        """Query usage records with optional filters."""
        return self._store.query(
            agent_id=agent_id,
            session_id=session_id,
            provider=provider,
            since=since,
            until=until,
            limit=limit,
        )

    def summary(
        self,
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated usage statistics."""
        return self._store.summary(
            agent_id=agent_id,
            session_id=session_id,
            group_by=group_by,
        )

    def reset(self) -> int:
        """Delete all usage records. Returns count of deleted rows."""
        return self._store.reset()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._store.close()


# ------------------------------------------------------------------ Singleton

_tracker: TokenTracker | None = None


def get_tracker(db_path: Path | str | None = None) -> TokenTracker:
    """Get the global TokenTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker(db_path)
    return _tracker
