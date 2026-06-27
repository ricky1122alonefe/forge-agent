"""Minimal in-process metrics collector (counter / gauge / histogram)."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe, in-process metrics. For multi-node, swap with Prometheus client."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def incr(self, name: str, value: float = 1.0, **tags: Any) -> None:
        with self._lock:
            self._counters[_key(name, tags)] += value

    def gauge(self, name: str, value: float, **tags: Any) -> None:
        with self._lock:
            self._gauges[_key(name, tags)] = value

    def observe(self, name: str, value: float, **tags: Any) -> None:
        with self._lock:
            self._histograms[_key(name, tags)].append(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "avg": (sum(v) / len(v)) if v else 0.0,
                        "max": max(v) if v else 0.0,
                        "min": min(v) if v else 0.0,
                    }
                    for k, v in self._histograms.items()
                },
            }


def _key(name: str, tags: dict[str, Any]) -> str:
    if not tags:
        return name
    tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
    return f"{name}{{{tag_str}}}"
