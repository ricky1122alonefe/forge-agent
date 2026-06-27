"""Tests for metrics data access layer."""

from __future__ import annotations

import pytest

from forge_agent.dashboard.data.metrics import MetricsDataSource, MetricsSnapshot


class TestMetricsDataSource:
    """Tests for MetricsDataSource."""

    def test_snapshot_empty(self) -> None:
        source = MetricsDataSource()
        snapshot = source.snapshot()
        assert isinstance(snapshot, MetricsSnapshot)
        assert isinstance(snapshot.counters, dict)
        assert isinstance(snapshot.gauges, dict)
        assert isinstance(snapshot.histograms, dict)

    def test_snapshot_after_incr(self) -> None:
        source = MetricsDataSource()
        source.collector.incr("test_requests", 1.0)
        snapshot = source.snapshot()
        assert "test_requests" in snapshot.counters
        assert snapshot.counters["test_requests"] == 1.0

    def test_snapshot_after_gauge(self) -> None:
        source = MetricsDataSource()
        source.collector.gauge("test_active", 42.0)
        snapshot = source.snapshot()
        assert "test_active" in snapshot.gauges
        assert snapshot.gauges["test_active"] == 42.0

    def test_snapshot_after_observe(self) -> None:
        source = MetricsDataSource()
        source.collector.observe("test_latency", 100.0)
        source.collector.observe("test_latency", 200.0)
        snapshot = source.snapshot()
        assert "test_latency" in snapshot.histograms
        h = snapshot.histograms["test_latency"]
        assert h["count"] == 2
        assert h["avg"] == 150.0


class TestMetricsSnapshot:
    """Tests for MetricsSnapshot."""

    def test_to_dict(self) -> None:
        snapshot = MetricsSnapshot(
            counters={"requests": 10.0},
            gauges={"active": 5.0},
            histograms={"latency": {"count": 3, "avg": 50.0, "max": 100.0, "min": 10.0}},
        )
        d = snapshot.to_dict()
        assert d["counters"]["requests"] == 10.0
        assert d["gauges"]["active"] == 5.0

    def test_total_requests(self) -> None:
        snapshot = MetricsSnapshot(
            counters={"http_requests": 10.0, "api_requests": 5.0, "errors": 2.0},
        )
        assert snapshot.total_requests == 15.0

    def test_total_errors(self) -> None:
        snapshot = MetricsSnapshot(
            counters={"http_errors": 3.0, "validation_error": 1.0, "requests": 10.0},
        )
        assert snapshot.total_errors == 4.0
