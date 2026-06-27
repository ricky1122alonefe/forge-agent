"""Tests for OpenTelemetry exporter adapter.

Tests work WITHOUT opentelemetry installed — they mock the OTel SDK
to verify the adapter logic (attribute mapping, status mapping,
export flow, install/uninstall hooks).
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from forge_agent.observability.otel_exporter import (
    OTelExporter,
    _build_otel_attributes,
    _get_otel_span_kind,
    _get_otel_status,
    get_installed_exporter,
    install_otel_exporter,
    is_otel_available,
    uninstall_otel_exporter,
)
from forge_agent.observability.trace import (
    Span,
    SpanStatus,
    SpanType,
    Trace,
    TraceManager,
    reset_trace_manager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_span(
    name: str = "test-span",
    span_type: SpanType = SpanType.AGENT,
    status: SpanStatus = SpanStatus.OK,
    parent_span_id: str = "",
    error_message: str = "",
    attributes: dict | None = None,
    events: list | None = None,
    span_id: str = "span_abc123",
) -> Span:
    span = Span(
        span_id=span_id,
        trace_id="trace_xyz789",
        name=name,
        span_type=span_type,
        parent_span_id=parent_span_id,
        start_time="2026-06-27T10:00:00+00:00",
        end_time="2026-06-27T10:00:01+00:00",
        duration_ms=1000.0,
        status=status,
        attributes=attributes or {},
        events=events or [],
        error_message=error_message,
    )
    return span


def _make_trace(spans: list[Span] | None = None) -> Trace:
    trace = Trace(
        trace_id="trace_xyz789",
        pipeline_id="test-pipeline",
        start_time="2026-06-27T10:00:00+00:00",
        end_time="2026-06-27T10:00:05+00:00",
        duration_ms=5000.0,
        spans=spans or [],
    )
    return trace


# ===========================================================================
# Test: is_otel_available
# ===========================================================================


class TestIsOtelAvailable:
    def test_returns_bool(self):
        result = is_otel_available()
        assert isinstance(result, bool)

    def test_reflects_module_state(self):
        """Should match whether opentelemetry is actually importable."""
        try:
            import opentelemetry  # noqa: F401
            assert is_otel_available() is True
        except ImportError:
            assert is_otel_available() is False


# ===========================================================================
# Test: _build_otel_attributes
# ===========================================================================


class TestBuildOtelAttributes:
    def test_basic_attributes(self):
        span = _make_span()
        attrs = _build_otel_attributes(span)
        assert attrs["forge_agent.span_id"] == "span_abc123"
        assert attrs["forge_agent.trace_id"] == "trace_xyz789"
        assert attrs["forge_agent.span_type"] == "agent"
        assert attrs["forge_agent.duration_ms"] == 1000.0

    def test_parent_span_id_included(self):
        span = _make_span(parent_span_id="span_parent1")
        attrs = _build_otel_attributes(span)
        assert attrs["forge_agent.parent_span_id"] == "span_parent1"

    def test_no_parent_span_id_when_empty(self):
        span = _make_span(parent_span_id="")
        attrs = _build_otel_attributes(span)
        assert "forge_agent.parent_span_id" not in attrs

    def test_error_message_included(self):
        span = _make_span(error_message="something broke")
        attrs = _build_otel_attributes(span)
        assert attrs["forge_agent.error"] == "something broke"

    def test_user_attributes_merged(self):
        span = _make_span(attributes={"tokens_in": 150, "model": "gpt-4"})
        attrs = _build_otel_attributes(span)
        assert attrs["tokens_in"] == 150
        assert attrs["model"] == "gpt-4"

    def test_non_primitive_attributes_stringified(self):
        span = _make_span(attributes={"config": {"nested": True}})
        attrs = _build_otel_attributes(span)
        assert isinstance(attrs["config"], str)

    def test_bool_attribute_preserved(self):
        span = _make_span(attributes={"success": True})
        attrs = _build_otel_attributes(span)
        assert attrs["success"] is True

    def test_float_attribute_preserved(self):
        span = _make_span(attributes={"cost": 0.005})
        attrs = _build_otel_attributes(span)
        assert attrs["cost"] == 0.005


# ===========================================================================
# Test: _get_otel_status (without real OTel)
# ===========================================================================


class TestGetOtelStatus:
    def test_returns_none_when_otel_unavailable(self):
        """When OTel is not installed, returns None."""
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = False
            result = _get_otel_status(SpanStatus.OK)
            assert result is None
        finally:
            mod._OTEL_AVAILABLE = original

    def test_returns_none_for_all_statuses_when_unavailable(self):
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = False
            for status in SpanStatus:
                assert _get_otel_status(status) is None
        finally:
            mod._OTEL_AVAILABLE = original


# ===========================================================================
# Test: _get_otel_span_kind (without real OTel)
# ===========================================================================


class TestGetOtelSpanKind:
    def test_returns_none_when_otel_unavailable(self):
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = False
            result = _get_otel_span_kind(SpanType.AGENT)
            assert result is None
        finally:
            mod._OTEL_AVAILABLE = original


# ===========================================================================
# Test: OTelExporter (no-op mode — OTel not installed)
# ===========================================================================


class TestOTelExporterNoOp:
    """Tests for OTelExporter when opentelemetry is NOT available."""

    def test_export_span_returns_none_without_otel(self):
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = False
            exporter = OTelExporter(service_name="test")
            span = _make_span()
            result = exporter.export_span(span)
            assert result is None
        finally:
            mod._OTEL_AVAILABLE = original

    def test_export_trace_returns_empty_without_otel(self):
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = False
            exporter = OTelExporter(service_name="test")
            trace = _make_trace([_make_span()])
            result = exporter.export_trace(trace)
            assert result == []
        finally:
            mod._OTEL_AVAILABLE = original

    def test_export_traces_returns_zero_without_otel(self):
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = False
            exporter = OTelExporter(service_name="test")
            result = exporter.export_traces([_make_trace([_make_span()])])
            assert result == 0
        finally:
            mod._OTEL_AVAILABLE = original

    def test_service_name_stored(self):
        exporter = OTelExporter(service_name="my-service")
        assert exporter.service_name == "my-service"


# ===========================================================================
# Test: OTelExporter (mocked OTel SDK)
# ===========================================================================


class TestOTelExporterWithMock:
    """Tests with a mocked OTel SDK to verify adapter logic."""

    def _make_mock_exporter(self) -> OTelExporter:
        """Create an OTelExporter with a mocked tracer."""
        exporter = OTelExporter.__new__(OTelExporter)
        exporter.service_name = "test-service"
        mock_tracer = MagicMock()
        mock_otel_span = MagicMock()
        mock_tracer.start_span.return_value = mock_otel_span
        exporter._tracer = mock_tracer
        return exporter

    def test_export_span_creates_otel_span(self):
        exporter = self._make_mock_exporter()
        span = _make_span(name="my-agent", span_type=SpanType.AGENT)
        result = exporter.export_span(span)
        exporter._tracer.start_span.assert_called_once()
        assert result is not None

    def test_export_span_sets_status(self):
        exporter = self._make_mock_exporter()
        span = _make_span(status=SpanStatus.ERROR, error_message="fail")
        exporter.export_span(span)
        mock_otel_span = exporter._tracer.start_span.return_value
        mock_otel_span.set_status.assert_called_once()

    def test_export_span_adds_events(self):
        exporter = self._make_mock_exporter()
        events = [{"name": "llm_call", "attributes": {"model": "gpt-4"}}]
        span = _make_span(events=events)
        exporter.export_span(span)
        mock_otel_span = exporter._tracer.start_span.return_value
        mock_otel_span.add_event.assert_called_once_with(
            name="llm_call", attributes={"model": "gpt-4"}
        )

    def test_export_span_ends_span(self):
        exporter = self._make_mock_exporter()
        span = _make_span()
        exporter.export_span(span)
        mock_otel_span = exporter._tracer.start_span.return_value
        mock_otel_span.end.assert_called_once()

    def test_export_trace_exports_all_spans(self):
        exporter = self._make_mock_exporter()
        spans = [
            _make_span(name="span-1"),
            _make_span(name="span-2"),
            _make_span(name="span-3"),
        ]
        trace = _make_trace(spans)
        result = exporter.export_trace(trace)
        assert len(result) == 3

    def test_export_trace_handles_parent_child(self):
        exporter = self._make_mock_exporter()
        parent = _make_span(name="parent", span_id="span_parent")
        child = _make_span(name="child", span_id="span_child", parent_span_id="span_parent")
        trace = _make_trace([parent, child])
        result = exporter.export_trace(trace)
        assert len(result) == 2

    def test_export_traces_counts_spans(self):
        exporter = self._make_mock_exporter()
        t1 = _make_trace([_make_span(name="a"), _make_span(name="b")])
        t2 = _make_trace([_make_span(name="c")])
        count = exporter.export_traces([t1, t2])
        assert count == 3

    def test_export_span_with_no_events(self):
        exporter = self._make_mock_exporter()
        span = _make_span(events=[])
        exporter.export_span(span)
        mock_otel_span = exporter._tracer.start_span.return_value
        mock_otel_span.add_event.assert_not_called()

    def test_export_span_ok_status_no_error_message(self):
        exporter = self._make_mock_exporter()
        span = _make_span(status=SpanStatus.OK, error_message="")
        exporter.export_span(span)
        mock_otel_span = exporter._tracer.start_span.return_value
        # set_status called with just status, no error message
        mock_otel_span.set_status.assert_called_once()


# ===========================================================================
# Test: install / uninstall hooks
# ===========================================================================


class TestInstallUninstall:

    def setup_method(self):
        reset_trace_manager()
        uninstall_otel_exporter()

    def teardown_method(self):
        reset_trace_manager()
        uninstall_otel_exporter()

    def test_install_returns_exporter(self):
        exporter = install_otel_exporter(service_name="test")
        assert isinstance(exporter, OTelExporter)
        assert exporter.service_name == "test"

    def test_get_installed_exporter_after_install(self):
        assert get_installed_exporter() is None
        install_otel_exporter(service_name="test")
        assert get_installed_exporter() is not None

    def test_uninstall_clears_exporter(self):
        install_otel_exporter(service_name="test")
        assert get_installed_exporter() is not None
        uninstall_otel_exporter()
        assert get_installed_exporter() is None

    def test_install_patches_end_trace(self):
        mgr = TraceManager()
        install_otel_exporter(service_name="test", manager=mgr)
        # end_trace should now be patched
        assert mgr.end_trace.__name__ == "_patched_end_trace"

    def test_uninstall_restores_end_trace(self):
        mgr = TraceManager()
        original_name = mgr.end_trace.__name__
        install_otel_exporter(service_name="test", manager=mgr)
        assert mgr.end_trace.__name__ != original_name
        uninstall_otel_exporter(manager=mgr)
        assert mgr.end_trace.__name__ == original_name

    def test_patched_end_trace_still_returns_trace(self):
        mgr = TraceManager()
        install_otel_exporter(service_name="test", manager=mgr)
        trace = mgr.start_trace(pipeline_id="test")
        result = mgr.end_trace()
        assert result is not None
        assert result.trace_id == trace.trace_id

    def test_patched_end_trace_exports(self):
        mgr = TraceManager()
        exporter = install_otel_exporter(service_name="test", manager=mgr)
        # Mock the export_trace method
        with patch.object(exporter, "export_trace") as mock_export:
            trace = mgr.start_trace(pipeline_id="test")
            span = trace.start_span("test-span")
            span.end()
            mgr.end_trace()
            mock_export.assert_called_once()

    def test_patched_end_trace_handles_export_failure(self):
        """Export failure should not break end_trace."""
        mgr = TraceManager()
        exporter = install_otel_exporter(service_name="test", manager=mgr)
        with patch.object(exporter, "export_trace", side_effect=RuntimeError("boom")):
            trace = mgr.start_trace(pipeline_id="test")
            trace.start_span("test-span").end()
            result = mgr.end_trace()
            # Should still return the trace
            assert result is not None

    def test_install_with_custom_tracer_provider(self):
        import forge_agent.observability.otel_exporter as mod
        original = mod._OTEL_AVAILABLE
        try:
            mod._OTEL_AVAILABLE = True
            mock_provider = MagicMock()
            mock_tracer = MagicMock()
            mock_provider.get_tracer.return_value = mock_tracer
            exporter = install_otel_exporter(
                service_name="custom",
                tracer_provider=mock_provider,
            )
            mock_provider.get_tracer.assert_called_once_with(
                "custom", instrumenting_library_version="0.3.0"
            )
        finally:
            mod._OTEL_AVAILABLE = original


# ===========================================================================
# Test: SpanType → OTel kind mapping
# ===========================================================================


class TestSpanTypeMapping:
    """Verify the mapping dict is complete."""

    def test_all_span_types_mapped(self):
        from forge_agent.observability.otel_exporter import _SPAN_TYPE_TO_OTEL_KIND
        for st in SpanType:
            assert st in _SPAN_TYPE_TO_OTEL_KIND, f"Missing mapping for {st}"

    def test_llm_maps_to_client(self):
        from forge_agent.observability.otel_exporter import _SPAN_TYPE_TO_OTEL_KIND
        assert _SPAN_TYPE_TO_OTEL_KIND[SpanType.LLM] == "CLIENT"

    def test_agent_maps_to_internal(self):
        from forge_agent.observability.otel_exporter import _SPAN_TYPE_TO_OTEL_KIND
        assert _SPAN_TYPE_TO_OTEL_KIND[SpanType.AGENT] == "INTERNAL"


# ===========================================================================
# Test: SpanStatus → OTel status mapping
# ===========================================================================


class TestStatusMapping:
    def test_all_statuses_mapped(self):
        from forge_agent.observability.otel_exporter import _STATUS_MAP
        for ss in SpanStatus:
            assert ss in _STATUS_MAP, f"Missing mapping for {ss}"

    def test_ok_maps_to_ok(self):
        from forge_agent.observability.otel_exporter import _STATUS_MAP
        assert _STATUS_MAP[SpanStatus.OK] == "OK"

    def test_error_maps_to_error(self):
        from forge_agent.observability.otel_exporter import _STATUS_MAP
        assert _STATUS_MAP[SpanStatus.ERROR] == "ERROR"

    def test_timeout_maps_to_error(self):
        from forge_agent.observability.otel_exporter import _STATUS_MAP
        assert _STATUS_MAP[SpanStatus.TIMEOUT] == "ERROR"

    def test_cancelled_maps_to_unset(self):
        from forge_agent.observability.otel_exporter import _STATUS_MAP
        assert _STATUS_MAP[SpanStatus.CANCELLED] == "UNSET"


# ===========================================================================
# Test: Integration with TraceManager
# ===========================================================================


class TestOtelIntegration:

    def setup_method(self):
        reset_trace_manager()
        uninstall_otel_exporter()

    def teardown_method(self):
        reset_trace_manager()
        uninstall_otel_exporter()

    def test_full_trace_export_flow(self):
        """End-to-end: create trace → add spans → end → verify export called."""
        mgr = TraceManager()
        exporter = install_otel_exporter(service_name="e2e-test", manager=mgr)

        with patch.object(exporter, "export_trace") as mock_export:
            trace = mgr.start_trace(pipeline_id="stock_analysis")
            s1 = trace.start_span("scraper", span_type=SpanType.AGENT)
            s1.set_attribute("tokens_in", 100)
            s1.end()
            s2 = trace.start_span("analyzer", span_type=SpanType.AGENT)
            s2.set_attribute("tokens_in", 200)
            s2.end()
            mgr.end_trace()

            mock_export.assert_called_once()
            exported_trace = mock_export.call_args[0][0]
            assert len(exported_trace.spans) == 2

    def test_export_empty_trace(self):
        exporter = OTelExporter.__new__(OTelExporter)
        exporter.service_name = "test"
        exporter._tracer = MagicMock()
        trace = _make_trace(spans=[])
        result = exporter.export_trace(trace)
        assert result == []

    def test_multiple_traces_exported(self):
        mgr = TraceManager()
        exporter = install_otel_exporter(service_name="multi", manager=mgr)
        export_calls = []

        with patch.object(exporter, "export_trace", side_effect=lambda t: export_calls.append(t)):
            t1 = mgr.start_trace(pipeline_id="p1")
            t1.start_span("s1").end()
            mgr.end_trace()

            t2 = mgr.start_trace(pipeline_id="p2")
            t2.start_span("s2").end()
            mgr.end_trace()

            assert len(export_calls) == 2
