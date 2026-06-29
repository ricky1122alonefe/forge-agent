"""Tests for T2.1.6 — Token Tracker & Usage Store."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.llm.protocol import LLMResponse
from forge_agent.llm.tracker import TokenTracker, estimate_cost
from forge_agent.llm.usage_store import SQLiteUsageStore, TokenUsage

# ------------------------------------------------------------------ Fixtures


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_usage.db"


@pytest.fixture
def store(tmp_db: Path) -> SQLiteUsageStore:
    return SQLiteUsageStore(tmp_db)


@pytest.fixture
def tracker(tmp_db: Path) -> TokenTracker:
    """Fresh tracker with temp DB (reset singleton)."""
    TokenTracker.reset_instance()
    t = TokenTracker(tmp_db)
    yield t
    t.close()
    TokenTracker.reset_instance()


def _make_response(
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    tokens_in: int = 100,
    tokens_out: int = 50,
    cost_usd: float | None = None,
) -> LLMResponse:
    return LLMResponse(
        content="hello",
        provider=provider,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
    )


# ------------------------------------------------------------------ TokenUsage dataclass


class TestTokenUsage:
    def test_basic_creation(self):
        u = TokenUsage(
            provider="deepseek",
            model="deepseek-chat",
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            timestamp="2026-06-27T10:00:00Z",
        )
        assert u.provider == "deepseek"
        assert u.total_tokens == 150

    def test_to_dict(self):
        u = TokenUsage(
            provider="deepseek",
            model="deepseek-chat",
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            timestamp="2026-06-27T10:00:00Z",
            agent_id="stock.monitor",
        )
        d = u.to_dict()
        assert d["provider"] == "deepseek"
        assert d["agent_id"] == "stock.monitor"
        assert d["tokens_in"] == 100

    def test_from_dict(self):
        d = {
            "provider": "openai",
            "model": "gpt-4",
            "tokens_in": 200,
            "tokens_out": 100,
            "cost_usd": 0.01,
            "timestamp": "2026-06-27T10:00:00Z",
        }
        u = TokenUsage.from_dict(d)
        assert u.provider == "openai"
        assert u.total_tokens == 300

    def test_metadata_default_empty(self):
        u = TokenUsage(
            provider="deepseek",
            model="deepseek-chat",
            tokens_in=10,
            tokens_out=5,
            cost_usd=0.0,
            timestamp="2026-06-27T10:00:00Z",
        )
        assert u.metadata == {}


# ------------------------------------------------------------------ SQLiteUsageStore


class TestSQLiteUsageStore:
    def test_insert_and_query(self, store: SQLiteUsageStore):
        u = TokenUsage(
            provider="deepseek",
            model="deepseek-chat",
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            timestamp="2026-06-27T10:00:00Z",
        )
        result = store.insert(u)
        assert result.id is not None
        records = store.query()
        assert len(records) == 1
        assert records[0].provider == "deepseek"

    def test_query_by_agent_id(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
                agent_id="stock.monitor",
            )
        )
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.002,
                timestamp="2026-06-27T10:01:00Z",
                agent_id="weather.check",
            )
        )
        records = store.query(agent_id="stock.monitor")
        assert len(records) == 1
        assert records[0].agent_id == "stock.monitor"

    def test_query_by_session_id(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
                session_id="gen_abc",
            )
        )
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.002,
                timestamp="2026-06-27T10:01:00Z",
                session_id="gen_xyz",
            )
        )
        records = store.query(session_id="gen_abc")
        assert len(records) == 1
        assert records[0].session_id == "gen_abc"

    def test_query_by_provider(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
            )
        )
        store.insert(
            TokenUsage(
                provider="openai",
                model="gpt-4",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.01,
                timestamp="2026-06-27T10:01:00Z",
            )
        )
        records = store.query(provider="openai")
        assert len(records) == 1
        assert records[0].provider == "openai"

    def test_query_by_time_range(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
            )
        )
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.002,
                timestamp="2026-06-27T12:00:00Z",
            )
        )
        records = store.query(since="2026-06-27T11:00:00Z")
        assert len(records) == 1
        assert records[0].tokens_in == 200

    def test_query_limit(self, store: SQLiteUsageStore):
        for i in range(10):
            store.insert(
                TokenUsage(
                    provider="deepseek",
                    model="deepseek-chat",
                    tokens_in=100,
                    tokens_out=50,
                    cost_usd=0.001,
                    timestamp=f"2026-06-27T10:{i:02d}:00Z",
                )
            )
        records = store.query(limit=5)
        assert len(records) == 5

    def test_query_empty_result(self, store: SQLiteUsageStore):
        records = store.query(agent_id="nonexistent")
        assert records == []

    def test_summary_basic(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
            )
        )
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.002,
                timestamp="2026-06-27T10:01:00Z",
            )
        )
        s = store.summary()
        assert s["call_count"] == 2
        assert s["total_tokens_in"] == 300
        assert s["total_tokens_out"] == 150
        assert s["total_tokens"] == 450
        assert abs(s["total_cost_usd"] - 0.003) < 1e-6

    def test_summary_group_by_provider(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
            )
        )
        store.insert(
            TokenUsage(
                provider="openai",
                model="gpt-4",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.01,
                timestamp="2026-06-27T10:01:00Z",
            )
        )
        s = store.summary(group_by="provider")
        assert "by_provider" in s
        assert "deepseek" in s["by_provider"]
        assert "openai" in s["by_provider"]
        assert s["by_provider"]["openai"]["cost_usd"] > s["by_provider"]["deepseek"]["cost_usd"]

    def test_summary_with_filter(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
                agent_id="stock.monitor",
            )
        )
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=200,
                tokens_out=100,
                cost_usd=0.002,
                timestamp="2026-06-27T10:01:00Z",
                agent_id="weather.check",
            )
        )
        s = store.summary(agent_id="stock.monitor")
        assert s["call_count"] == 1
        assert s["total_tokens_in"] == 100

    def test_reset(self, store: SQLiteUsageStore):
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
            )
        )
        count = store.reset()
        assert count == 1
        assert store.query() == []

    def test_metadata_json_roundtrip(self, store: SQLiteUsageStore):
        meta = {"attempt": 2, "retry_reason": "validation_failed"}
        store.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
                metadata=meta,
            )
        )
        records = store.query()
        assert records[0].metadata == meta

    def test_persistence_across_instances(self, tmp_db: Path):
        store1 = SQLiteUsageStore(tmp_db)
        store1.insert(
            TokenUsage(
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.001,
                timestamp="2026-06-27T10:00:00Z",
            )
        )
        store1.close()
        store2 = SQLiteUsageStore(tmp_db)
        records = store2.query()
        assert len(records) == 1
        store2.close()


# ------------------------------------------------------------------ estimate_cost


class TestEstimateCost:
    def test_known_model(self):
        cost = estimate_cost("deepseek-chat", 1_000_000, 1_000_000)
        assert abs(cost - 0.42) < 0.01  # 0.14 + 0.28

    def test_unknown_model(self):
        cost = estimate_cost("unknown-model-xyz", 1000, 500)
        assert cost == 0.0

    def test_prefix_match(self):
        cost = estimate_cost("gpt-4o-2024-05-13", 1_000_000, 0)
        assert cost > 0  # Should match "gpt-4o"

    def test_zero_tokens(self):
        cost = estimate_cost("deepseek-chat", 0, 0)
        assert cost == 0.0

    def test_local_model_free(self):
        cost = estimate_cost("qwen2.5:7b", 10000, 5000)
        assert cost == 0.0


# ------------------------------------------------------------------ TokenTracker


class TestTokenTracker:
    def test_record_basic(self, tracker: TokenTracker):
        resp = _make_response(tokens_in=100, tokens_out=50)
        usage = tracker.record(resp, agent_id="stock.monitor")
        assert usage.provider == "deepseek"
        assert usage.tokens_in == 100
        assert usage.agent_id == "stock.monitor"
        assert usage.id is not None

    def test_record_with_session_id(self, tracker: TokenTracker):
        resp = _make_response()
        usage = tracker.record(resp, session_id="gen_abc123")
        assert usage.session_id == "gen_abc123"

    def test_record_uses_provider_cost(self, tracker: TokenTracker):
        resp = _make_response(cost_usd=0.05)
        usage = tracker.record(resp)
        assert usage.cost_usd == 0.05

    def test_record_estimates_cost_when_none(self, tracker: TokenTracker):
        resp = _make_response(
            model="deepseek-chat",
            tokens_in=1_000_000,
            tokens_out=1_000_000,
            cost_usd=None,
        )
        usage = tracker.record(resp)
        assert usage.cost_usd > 0

    def test_query_after_record(self, tracker: TokenTracker):
        tracker.record(_make_response(), agent_id="stock.monitor")
        tracker.record(_make_response(), agent_id="weather.check")
        records = tracker.query(agent_id="stock.monitor")
        assert len(records) == 1

    def test_summary_after_records(self, tracker: TokenTracker):
        tracker.record(_make_response(tokens_in=100, tokens_out=50))
        tracker.record(_make_response(tokens_in=200, tokens_out=100))
        s = tracker.summary()
        assert s["call_count"] == 2
        assert s["total_tokens_in"] == 300

    def test_summary_group_by(self, tracker: TokenTracker):
        tracker.record(_make_response(provider="deepseek"))
        tracker.record(_make_response(provider="openai", model="gpt-4"))
        s = tracker.summary(group_by="provider")
        assert "by_provider" in s
        assert len(s["by_provider"]) == 2

    def test_reset(self, tracker: TokenTracker):
        tracker.record(_make_response())
        count = tracker.reset()
        assert count == 1
        assert tracker.query() == []

    def test_disabled_tracker(self, tracker: TokenTracker):
        tracker.enabled = False
        resp = _make_response()
        usage = tracker.record(resp)
        assert usage.id is None  # Not persisted
        assert tracker.query() == []

    def test_record_with_metadata(self, tracker: TokenTracker):
        resp = _make_response()
        tracker.record(resp, metadata={"attempt": 2})
        records = tracker.query()
        assert records[0].metadata == {"attempt": 2}


# ------------------------------------------------------------------ Integration with llm.chat()


class TestChatIntegration:
    """Test that llm.chat() auto-records token usage."""

    @pytest.mark.asyncio
    async def test_chat_records_usage(self, tracker: TokenTracker, tmp_db: Path):
        """Mock a chat call and verify tracker records it."""
        from forge_agent.llm.protocol import _record_usage

        resp = _make_response(tokens_in=150, tokens_out=75)
        _record_usage(resp, agent_id="test.agent", session_id="sess_1")

        records = tracker.query(agent_id="test.agent")
        assert len(records) == 1
        assert records[0].tokens_in == 150
        assert records[0].session_id == "sess_1"

    @pytest.mark.asyncio
    async def test_record_usage_no_tracker_available(self):
        """_record_usage should not raise even if tracker fails."""
        from forge_agent.llm.protocol import _record_usage

        TokenTracker.reset_instance()
        resp = _make_response()
        # Should not raise
        _record_usage(resp, agent_id="test")
