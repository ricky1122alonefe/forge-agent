"""Trace system — structured execution tracking for agents and pipelines.

Every pipeline execution gets a trace_id. Each agent run, observe/decide/act
step, and pipeline node becomes a Span within that trace.

Usage::

    from forge_agent.observability.trace import TraceManager, get_trace_manager

    mgr = get_trace_manager()
    trace = mgr.start_trace(pipeline_id="stock_analysis")
    span = trace.start_span("agent:stock.monitor", span_type="agent")
    span.set_attribute("tokens_in", 150)
    span.end()
    trace.end()

    # Query
    t = mgr.get_trace(trace.trace_id)
    print(t.summary())
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "trace") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class SpanType(str, Enum):
    PIPELINE = "pipeline"
    AGENT = "agent"
    OBSERVE = "observe"
    DECIDE = "decide"
    ACT = "act"
    REFLECT = "reflect"
    LEARN = "learn"
    FUNCTION = "function"
    AGGREGATOR = "aggregator"
    LLM = "llm"
    CUSTOM = "custom"


@dataclass
class Span:
    """A single unit of work within a trace."""

    span_id: str
    trace_id: str
    name: str
    span_type: SpanType = SpanType.CUSTOM
    parent_span_id: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_ms: float = 0.0
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""
    _start_perf: float = field(default=0.0, repr=False)

    def start(self) -> "Span":
        self._start_perf = time.perf_counter()
        self.start_time = _now_iso()
        return self

    def end(self, status: SpanStatus = SpanStatus.OK) -> "Span":
        self.end_time = _now_iso()
        self.duration_ms = round((time.perf_counter() - self._start_perf) * 1000, 2)
        self.status = status
        return self

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, **attrs: Any) -> None:
        self.events.append({
            "name": name,
            "timestamp": _now_iso(),
            "attributes": attrs,
        })

    def set_error(self, message: str) -> None:
        self.error_message = message
        self.status = SpanStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "span_type": self.span_type.value,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "error_message": self.error_message,
        }


@dataclass
class Trace:
    """A complete execution trace containing multiple spans."""

    trace_id: str
    pipeline_id: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_ms: float = 0.0
    spans: list[Span] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    _start_perf: float = field(default=0.0, repr=False)

    def start(self) -> "Trace":
        self._start_perf = time.perf_counter()
        self.start_time = _now_iso()
        return self

    def end(self) -> "Trace":
        self.end_time = _now_iso()
        self.duration_ms = round((time.perf_counter() - self._start_perf) * 1000, 2)
        return self

    def start_span(
        self,
        name: str,
        *,
        span_type: SpanType = SpanType.CUSTOM,
        parent_span_id: str = "",
    ) -> Span:
        span = Span(
            span_id=_new_id("span"),
            trace_id=self.trace_id,
            name=name,
            span_type=span_type,
            parent_span_id=parent_span_id,
        )
        span.start()
        self.spans.append(span)
        return span

    def get_span(self, span_id: str) -> Span | None:
        for s in self.spans:
            if s.span_id == span_id:
                return s
        return None

    def get_spans_by_type(self, span_type: SpanType) -> list[Span]:
        return [s for s in self.spans if s.span_type == span_type]

    def summary(self) -> dict[str, Any]:
        agent_spans = self.get_spans_by_type(SpanType.AGENT)
        error_spans = [s for s in self.spans if s.status == SpanStatus.ERROR]
        total_tokens_in = sum(
            s.attributes.get("tokens_in", 0) for s in self.spans
        )
        total_tokens_out = sum(
            s.attributes.get("tokens_out", 0) for s in self.spans
        )
        return {
            "trace_id": self.trace_id,
            "pipeline_id": self.pipeline_id,
            "duration_ms": self.duration_ms,
            "total_spans": len(self.spans),
            "agent_count": len(agent_spans),
            "error_count": len(error_spans),
            "errors": [s.error_message for s in error_spans if s.error_message],
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "span_types": {
                st.value: len(self.get_spans_by_type(st))
                for st in SpanType
                if self.get_spans_by_type(st)
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "pipeline_id": self.pipeline_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "spans": [s.to_dict() for s in self.spans],
        }


class TraceManager:
    """Manages traces for the current process.

    In-memory store. For distributed tracing, swap with an OTel exporter.
    """

    def __init__(self, max_traces: int = 1000) -> None:
        self._traces: dict[str, Trace] = {}
        self._max_traces = max_traces
        self._current_trace_id: str | None = None

    def start_trace(self, pipeline_id: str = "", **attrs: Any) -> Trace:
        trace = Trace(
            trace_id=_new_id("trace"),
            pipeline_id=pipeline_id,
            attributes=attrs,
        )
        trace.start()
        self._traces[trace.trace_id] = trace
        self._current_trace_id = trace.trace_id
        # Evict old traces if over limit
        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces, key=lambda k: self._traces[k].start_time)
            for k in oldest[: len(oldest) // 2]:
                del self._traces[k]
        return trace

    def end_trace(self, trace_id: str | None = None) -> Trace | None:
        tid = trace_id or self._current_trace_id
        if tid and tid in self._traces:
            trace = self._traces[tid]
            trace.end()
            if self._current_trace_id == tid:
                self._current_trace_id = None
            return trace
        return None

    def get_trace(self, trace_id: str) -> Trace | None:
        return self._traces.get(trace_id)

    @property
    def current_trace(self) -> Trace | None:
        if self._current_trace_id:
            return self._traces.get(self._current_trace_id)
        return None

    def list_traces(self, limit: int = 20) -> list[dict[str, Any]]:
        traces = sorted(
            self._traces.values(),
            key=lambda t: t.start_time,
            reverse=True,
        )
        return [
            {
                "trace_id": t.trace_id,
                "pipeline_id": t.pipeline_id,
                "start_time": t.start_time,
                "duration_ms": t.duration_ms,
                "span_count": len(t.spans),
            }
            for t in traces[:limit]
        ]

    def start_span(
        self,
        name: str,
        *,
        span_type: SpanType = SpanType.CUSTOM,
        trace: Trace | None = None,
        parent_span_id: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Start a span on the given trace (or current_trace if None)."""
        t = trace or self.current_trace
        if t is None:
            # No active trace — create a detached span
            span = Span(
                span_id=_new_id("span"),
                trace_id="",
                name=name,
                span_type=span_type,
                parent_span_id=parent_span_id,
            )
            if attributes:
                span.attributes.update(attributes)
            span.start()
            return span
        span = t.start_span(name, span_type=span_type, parent_span_id=parent_span_id)
        if attributes:
            span.attributes.update(attributes)
        return span

    def end_span(
        self,
        span: Span,
        *,
        status: str = "ok",
        error_message: str = "",
    ) -> None:
        """End a span with the given status."""
        span_status = SpanStatus.OK if status == "ok" else SpanStatus.ERROR
        span.end(status=span_status)
        if error_message:
            span.error_message = error_message

    def clear(self) -> int:
        count = len(self._traces)
        self._traces.clear()
        self._current_trace_id = None
        return count


# ------------------------------------------------------------------ Singleton

_manager: TraceManager | None = None


def get_trace_manager() -> TraceManager:
    global _manager
    if _manager is None:
        _manager = TraceManager()
    return _manager


def reset_trace_manager() -> None:
    global _manager
    if _manager is not None:
        _manager.clear()
    _manager = None
