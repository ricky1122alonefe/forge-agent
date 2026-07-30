"""Metrics data access layer for the dashboard.

Wraps MetricsCollector to provide dashboard-specific query methods.
Decoupled from FastAPI — pure data access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsSnapshot:
    """A snapshot of all current metrics."""

    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)

    @property
    def total_requests(self) -> float:
        return sum(v for k, v in self.counters.items() if "request" in k)

    @property
    def total_errors(self) -> float:
        return sum(v for k, v in self.counters.items() if "error" in k)


class MetricsDataSource:
    """Data access layer for metrics information.

    Wraps MetricsCollector to provide dashboard-specific queries.
    """

    def __init__(self) -> None:
        self._collector = None

    @property
    def collector(self):
        """Lazy access to the global MetricsCollector."""
        if self._collector is None:
            # Use a module-level singleton pattern
            self._collector = _get_metrics_collector()
        return self._collector

    def snapshot(self) -> MetricsSnapshot:
        """Get a snapshot of all current metrics."""
        raw = self.collector.snapshot()
        return MetricsSnapshot(
            counters=raw.get("counters", {}),
            gauges=raw.get("gauges", {}),
            histograms=raw.get("histograms", {}),
        )


# Module-level singleton for MetricsCollector
_collector_instance = None


def _get_metrics_collector():
    """Get or create the global MetricsCollector singleton."""
    global _collector_instance
    if _collector_instance is None:
        from forge_agent.observability.metrics import MetricsCollector

        _collector_instance = MetricsCollector()
    return _collector_instance
