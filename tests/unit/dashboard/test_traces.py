"""Tests for trace data access layer."""

from __future__ import annotations

import pytest

from forge_agent.dashboard.data.traces import TraceDataSource, TraceSummary, TraceDetail
from forge_agent.observability.trace import get_trace_manager, reset_trace_manager, SpanType


@pytest.fixture(autouse=True)
def clean_traces():
    """Reset trace manager before and after each test."""
    reset_trace_manager()
    yield
    reset_trace_manager()


class TestTraceDataSource:
    """Tests for TraceDataSource."""

    def test_list_traces_empty(self) -> None:
        source = TraceDataSource()
        traces = source.list_traces()
        assert traces == []

    def test_list_traces_with_data(self) -> None:
        mgr = get_trace_manager()
        trace = mgr.start_trace(pipeline_id="test_pipeline")
        trace.start_span("agent:test", span_type=SpanType.AGENT)
        mgr.end_trace()

        source = TraceDataSource()
        traces = source.list_traces()
        assert len(traces) == 1
        assert traces[0].pipeline_id == "test_pipeline"

    def test_get_trace_not_found(self) -> None:
        source = TraceDataSource()
        result = source.get_trace("nonexistent")
        assert result is None

    def test_get_trace_detail(self) -> None:
        mgr = get_trace_manager()
        trace = mgr.start_trace(pipeline_id="test_pipeline")
        span = trace.start_span("agent:test", span_type=SpanType.AGENT)
        span.set_attribute("tokens_in", 100)
        span.end()
        mgr.end_trace()

        source = TraceDataSource()
        detail = source.get_trace(trace.trace_id)
        assert detail is not None
        assert detail.trace_id == trace.trace_id
        assert detail.pipeline_id == "test_pipeline"
        assert len(detail.spans) == 1
        assert detail.spans[0]["name"] == "agent:test"

    def test_get_traces_for_agent(self) -> None:
        mgr = get_trace_manager()
        trace = mgr.start_trace(pipeline_id="test")
        trace.start_span("agent:stock.monitor", span_type=SpanType.AGENT)
        mgr.end_trace()

        trace2 = mgr.start_trace(pipeline_id="other")
        trace2.start_span("agent:other.agent", span_type=SpanType.AGENT)
        mgr.end_trace()

        source = TraceDataSource()
        traces = source.get_traces_for_agent("stock.monitor")
        assert len(traces) == 1
        assert traces[0].pipeline_id == "test"

    def test_trace_summary_to_dict(self) -> None:
        summary = TraceSummary(
            trace_id="trace_abc",
            pipeline_id="test",
            start_time="2026-06-27T00:00:00",
            duration_ms=100.5,
            span_count=3,
            error_count=0,
        )
        d = summary.to_dict()
        assert d["trace_id"] == "trace_abc"
        assert d["span_count"] == 3

    def test_trace_detail_to_dict(self) -> None:
        detail = TraceDetail(
            trace_id="trace_abc",
            pipeline_id="test",
            start_time="2026-06-27T00:00:00",
            end_time="2026-06-27T00:00:01",
            duration_ms=1000.0,
            spans=[{"span_id": "span_1", "name": "test"}],
        )
        d = detail.to_dict()
        assert d["trace_id"] == "trace_abc"
        assert len(d["spans"]) == 1

    def test_error_count_in_summary(self) -> None:
        mgr = get_trace_manager()
        trace = mgr.start_trace(pipeline_id="test")
        span = trace.start_span("failing_op", span_type=SpanType.FUNCTION)
        span.set_error("something broke")
        from forge_agent.observability.trace import SpanStatus
        span.end(status=SpanStatus.ERROR)
        mgr.end_trace()

        source = TraceDataSource()
        traces = source.list_traces()
        assert len(traces) == 1
        assert traces[0].error_count == 1
