"""Trace data access layer for the dashboard.

Wraps TraceManager to provide dashboard-friendly query methods.
Decoupled from FastAPI — pure data access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceSummary:
    """Lightweight trace summary for list views."""

    trace_id: str
    pipeline_id: str
    start_time: str
    duration_ms: float
    span_count: int
    error_count: int

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class TraceDetail:
    """Full trace detail with all spans."""

    trace_id: str
    pipeline_id: str
    start_time: str
    end_time: str
    duration_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)
    spans: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


class TraceDataSource:
    """Data access layer for trace information.

    Wraps TraceManager to provide dashboard-specific queries.
    """

    def __init__(self) -> None:
        self._manager = None

    @property
    def manager(self):
        """Lazy access to the global TraceManager."""
        if self._manager is None:
            from forge_agent.observability.trace import get_trace_manager
            self._manager = get_trace_manager()
        return self._manager

    def list_traces(self, limit: int = 50) -> list[TraceSummary]:
        """List recent traces as summaries."""
        raw = self.manager.list_traces(limit=limit)
        results = []
        for item in raw:
            trace = self.manager.get_trace(item["trace_id"])
            error_count = 0
            if trace:
                error_count = len([s for s in trace.spans if s.status.value == "error"])
            results.append(TraceSummary(
                trace_id=item["trace_id"],
                pipeline_id=item.get("pipeline_id", ""),
                start_time=item.get("start_time", ""),
                duration_ms=item.get("duration_ms", 0.0),
                span_count=item.get("span_count", 0),
                error_count=error_count,
            ))
        return results

    def get_trace(self, trace_id: str) -> TraceDetail | None:
        """Get full trace detail by ID."""
        trace = self.manager.get_trace(trace_id)
        if trace is None:
            return None
        return TraceDetail(
            trace_id=trace.trace_id,
            pipeline_id=trace.pipeline_id,
            start_time=trace.start_time,
            end_time=trace.end_time,
            duration_ms=trace.duration_ms,
            attributes=trace.attributes,
            spans=[s.to_dict() for s in trace.spans],
        )

    def get_traces_for_agent(self, agent_id: str, limit: int = 20) -> list[TraceSummary]:
        """Get traces that contain spans for a specific agent."""
        all_traces = self.list_traces(limit=200)
        results = []
        for summary in all_traces:
            trace = self.manager.get_trace(summary.trace_id)
            if trace is None:
                continue
            has_agent = any(
                agent_id in s.name for s in trace.spans
            )
            if has_agent:
                results.append(summary)
                if len(results) >= limit:
                    break
        return results
