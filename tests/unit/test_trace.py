"""Tests for the Trace system (observability/trace.py)."""

from __future__ import annotations

import pytest

from forge_agent.observability.trace import (
    Span,
    SpanStatus,
    SpanType,
    Trace,
    TraceManager,
    _new_id,
    get_trace_manager,
    reset_trace_manager,
)


# ------------------------------------------------------------------ Helpers


def _make_span(name: str = "test", span_type: SpanType = SpanType.CUSTOM) -> Span:
    return Span(span_id=_new_id("span"), trace_id="trace_abc", name=name, span_type=span_type)


# ------------------------------------------------------------------ Span


class TestSpan:
    def test_start_end(self):
        span = _make_span()
        span.start()
        assert span.start_time
        span.end()
        assert span.end_time
        assert span.duration_ms >= 0
        assert span.status == SpanStatus.OK

    def test_end_with_error(self):
        span = _make_span()
        span.start()
        span.end(status=SpanStatus.ERROR)
        assert span.status == SpanStatus.ERROR

    def test_set_attribute(self):
        span = _make_span()
        span.set_attribute("tokens_in", 100)
        assert span.attributes["tokens_in"] == 100

    def test_add_event(self):
        span = _make_span()
        span.add_event("llm_call", model="deepseek-chat")
        assert len(span.events) == 1
        assert span.events[0]["name"] == "llm_call"
        assert span.events[0]["attributes"]["model"] == "deepseek-chat"

    def test_set_error(self):
        span = _make_span()
        span.set_error("something broke")
        assert span.error_message == "something broke"
        assert span.status == SpanStatus.ERROR

    def test_to_dict(self):
        span = _make_span("my_span", SpanType.AGENT)
        span.start()
        span.end()
        d = span.to_dict()
        assert d["name"] == "my_span"
        assert d["span_type"] == "agent"
        assert d["trace_id"] == "trace_abc"
        assert "duration_ms" in d


# ------------------------------------------------------------------ Trace


class TestTrace:
    def test_start_end(self):
        trace = Trace(trace_id="trace_test")
        trace.start()
        assert trace.start_time
        trace.end()
        assert trace.end_time
        assert trace.duration_ms >= 0

    def test_start_span(self):
        trace = Trace(trace_id="trace_test")
        trace.start()
        span = trace.start_span("agent:stock", span_type=SpanType.AGENT)
        assert span.trace_id == "trace_test"
        assert span.name == "agent:stock"
        assert span.span_type == SpanType.AGENT
        assert span in trace.spans

    def test_get_span(self):
        trace = Trace(trace_id="trace_test")
        span = trace.start_span("test")
        found = trace.get_span(span.span_id)
        assert found is span
        assert trace.get_span("nonexistent") is None

    def test_get_spans_by_type(self):
        trace = Trace(trace_id="trace_test")
        trace.start_span("a", span_type=SpanType.AGENT)
        trace.start_span("b", span_type=SpanType.OBSERVE)
        trace.start_span("c", span_type=SpanType.AGENT)
        agents = trace.get_spans_by_type(SpanType.AGENT)
        assert len(agents) == 2

    def test_summary(self):
        trace = Trace(trace_id="trace_test", pipeline_id="pipe1")
        trace.start()
        trace.start_span("a", span_type=SpanType.AGENT)
        s = trace.start_span("b", span_type=SpanType.FUNCTION)
        s.start()
        s.end(status=SpanStatus.ERROR)
        s.set_error("oops")
        trace.end()
        summary = trace.summary()
        assert summary["trace_id"] == "trace_test"
        assert summary["pipeline_id"] == "pipe1"
        assert summary["agent_count"] == 1
        assert summary["error_count"] == 1
        assert "oops" in summary["errors"]

    def test_to_dict(self):
        trace = Trace(trace_id="trace_test")
        trace.start()
        trace.start_span("a")
        trace.end()
        d = trace.to_dict()
        assert d["trace_id"] == "trace_test"
        assert len(d["spans"]) == 1


# ------------------------------------------------------------------ TraceManager


class TestTraceManager:
    def setup_method(self):
        reset_trace_manager()

    def teardown_method(self):
        reset_trace_manager()

    def test_start_and_get_trace(self):
        mgr = TraceManager()
        trace = mgr.start_trace(pipeline_id="test_pipe")
        assert trace.pipeline_id == "test_pipe"
        assert mgr.get_trace(trace.trace_id) is trace

    def test_current_trace(self):
        mgr = TraceManager()
        assert mgr.current_trace is None
        trace = mgr.start_trace()
        assert mgr.current_trace is trace

    def test_end_trace(self):
        mgr = TraceManager()
        trace = mgr.start_trace()
        ended = mgr.end_trace()
        assert ended is trace
        assert ended.end_time
        assert mgr.current_trace is None

    def test_end_trace_by_id(self):
        mgr = TraceManager()
        trace = mgr.start_trace()
        ended = mgr.end_trace(trace.trace_id)
        assert ended is trace

    def test_end_trace_nonexistent(self):
        mgr = TraceManager()
        assert mgr.end_trace("nonexistent") is None

    def test_list_traces(self):
        mgr = TraceManager()
        mgr.start_trace(pipeline_id="a")
        mgr.start_trace(pipeline_id="b")
        traces = mgr.list_traces()
        assert len(traces) == 2
        # Most recent first
        assert traces[0]["pipeline_id"] == "b"

    def test_list_traces_limit(self):
        mgr = TraceManager()
        for i in range(5):
            mgr.start_trace(pipeline_id=f"p{i}")
        traces = mgr.list_traces(limit=3)
        assert len(traces) == 3

    def test_clear(self):
        mgr = TraceManager()
        mgr.start_trace()
        mgr.start_trace()
        count = mgr.clear()
        assert count == 2
        assert mgr.current_trace is None
        assert mgr.list_traces() == []

    def test_eviction(self):
        mgr = TraceManager(max_traces=4)
        for i in range(5):
            mgr.start_trace(pipeline_id=f"p{i}")
        # Should have evicted some
        assert len(mgr._traces) <= 4

    def test_start_span_with_trace(self):
        mgr = TraceManager()
        trace = mgr.start_trace()
        span = mgr.start_span("test", trace=trace, span_type=SpanType.AGENT)
        assert span.trace_id == trace.trace_id
        assert span in trace.spans

    def test_start_span_current_trace(self):
        mgr = TraceManager()
        trace = mgr.start_trace()
        span = mgr.start_span("test")
        assert span.trace_id == trace.trace_id

    def test_start_span_no_trace(self):
        mgr = TraceManager()
        span = mgr.start_span("detached")
        assert span.trace_id == ""

    def test_start_span_with_attributes(self):
        mgr = TraceManager()
        trace = mgr.start_trace()
        span = mgr.start_span("test", trace=trace, attributes={"key": "val"})
        assert span.attributes["key"] == "val"

    def test_end_span_ok(self):
        mgr = TraceManager()
        span = mgr.start_span("test")
        mgr.end_span(span, status="ok")
        assert span.status == SpanStatus.OK
        assert span.end_time

    def test_end_span_error(self):
        mgr = TraceManager()
        span = mgr.start_span("test")
        mgr.end_span(span, status="error", error_message="fail")
        assert span.status == SpanStatus.ERROR
        assert span.error_message == "fail"


# ------------------------------------------------------------------ Singleton


class TestSingleton:
    def setup_method(self):
        reset_trace_manager()

    def teardown_method(self):
        reset_trace_manager()

    def test_get_trace_manager_returns_same(self):
        mgr1 = get_trace_manager()
        mgr2 = get_trace_manager()
        assert mgr1 is mgr2

    def test_reset_trace_manager(self):
        mgr1 = get_trace_manager()
        reset_trace_manager()
        mgr2 = get_trace_manager()
        assert mgr1 is not mgr2
