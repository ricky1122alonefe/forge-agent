"""OpenTelemetry exporter adapter — bridges forge-agent traces to OTel backends.

When ``opentelemetry`` is installed, traces/spans are forwarded to any
configured OTel exporter (Jaeger, Zipkin, OTLP, etc.).  When the package
is **not** installed, all public functions degrade gracefully (no-op).

Usage::

    from forge_agent.observability.otel_exporter import (
        OTelExporter,
        install_otel_exporter,
        is_otel_available,
    )

    if is_otel_available():
        install_otel_exporter(service_name="my-agents")

    # traces are now auto-exported when ended via TraceManager
"""

from __future__ import annotations

import logging
from typing import Any

from forge_agent.observability.trace import (
    Span,
    SpanStatus,
    SpanType,
    Trace,
    TraceManager,
    get_trace_manager,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------

_OTEL_AVAILABLE = False
_tracer: Any = None
_otel_trace: Any = None
_otel_span_module: Any = None
_otel_status_module: Any = None
_otel_attributes: Any = None

try:
    from opentelemetry import trace as _otel_trace_mod
    from opentelemetry import trace as _otel_span_mod  # noqa: F811
    from opentelemetry.trace import StatusCode as _StatusCode
    from opentelemetry.trace import SpanKind as _SpanKind

    _otel_trace = _otel_trace_mod
    _otel_span_module = _otel_span_mod
    _otel_status_module = _StatusCode
    _otel_available = True
except ImportError:  # pragma: no cover
    pass


def is_otel_available() -> bool:
    """Return True if opentelemetry packages are installed."""
    return _OTEL_AVAILABLE


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

_SPAN_TYPE_TO_OTEL_KIND: dict[SpanType, str] = {
    SpanType.PIPELINE: "INTERNAL",
    SpanType.AGENT: "INTERNAL",
    SpanType.OBSERVE: "INTERNAL",
    SpanType.DECIDE: "INTERNAL",
    SpanType.ACT: "INTERNAL",
    SpanType.REFLECT: "INTERNAL",
    SpanType.LEARN: "INTERNAL",
    SpanType.FUNCTION: "INTERNAL",
    SpanType.AGGREGATOR: "INTERNAL",
    SpanType.LLM: "CLIENT",
    SpanType.CUSTOM: "INTERNAL",
}

_STATUS_MAP: dict[SpanStatus, str] = {
    SpanStatus.OK: "OK",
    SpanStatus.ERROR: "ERROR",
    SpanStatus.TIMEOUT: "ERROR",
    SpanStatus.CANCELLED: "UNSET",
}


def _get_otel_span_kind(span_type: SpanType) -> Any:
    """Map SpanType to OTel SpanKind."""
    if not _OTEL_AVAILABLE:
        return None
    kind_name = _SPAN_TYPE_TO_OTEL_KIND.get(span_type, "INTERNAL")
    return getattr(_SpanKind, kind_name, _SpanKind.INTERNAL)


def _get_otel_status(span_status: SpanStatus) -> Any:
    """Map SpanStatus to OTel StatusCode."""
    if not _OTEL_AVAILABLE:
        return None
    status_name = _STATUS_MAP.get(span_status, "UNSET")
    return getattr(_StatusCode, status_name, _StatusCode.UNSET)


# ---------------------------------------------------------------------------
# OTelExporter
# ---------------------------------------------------------------------------


class OTelExporter:
    """Adapter that exports forge-agent Trace/Span objects to OpenTelemetry.

    Parameters
    ----------
    service_name:
        Logical service name reported to OTel backend.
    tracer_provider:
        Optional custom TracerProvider.  When *None*, the global OTel
        provider is used.
    """

    def __init__(
        self,
        service_name: str = "forge-agent",
        tracer_provider: Any | None = None,
    ) -> None:
        if not _OTEL_AVAILABLE:
            log.debug("opentelemetry not installed — OTelExporter is a no-op")
            self._tracer = None
            self.service_name = service_name
            return

        if tracer_provider is not None:
            self._tracer = tracer_provider.get_tracer(
                service_name, instrumenting_library_version="0.3.0"
            )
        else:
            self._tracer = _otel_trace.get_tracer(
                service_name, instrumenting_library_version="0.3.0"
            )
        self.service_name = service_name

    # --------------------------------------------------------- public API

    def export_span(self, span: Span, parent_otel_span: Any | None = None) -> Any | None:
        """Export a single forge-agent Span to OTel.

        Returns the OTel span object (or None if OTel unavailable).
        """
        if self._tracer is None:
            return None

        kind = _get_otel_span_kind(span.span_type)
        ctx = None
        if parent_otel_span is not None and _OTEL_AVAILABLE:
            from opentelemetry import context as otel_context
            from opentelemetry.trace import set_span_in_context

            ctx = set_span_in_context(parent_otel_span)

        otel_span = self._tracer.start_span(
            name=span.name,
            kind=kind,
            context=ctx,
            attributes=_build_otel_attributes(span),
        )

        # Set status
        otel_status = _get_otel_status(span.status)
        if span.error_message:
            otel_span.set_status(otel_status, span.error_message)
        else:
            otel_span.set_status(otel_status)

        # Add events
        for event in span.events:
            otel_span.add_event(
                name=event.get("name", "unknown"),
                attributes=event.get("attributes", {}),
            )

        otel_span.end()
        return otel_span

    def export_trace(self, trace: Trace) -> list[Any]:
        """Export a complete Trace (all its spans) to OTel.

        Returns list of OTel span objects.
        """
        if self._tracer is None:
            return []

        otel_spans: list[Any] = []
        # Build parent mapping
        span_id_to_otel: dict[str, Any] = {}

        for span in trace.spans:
            parent_otel = None
            if span.parent_span_id and span.parent_span_id in span_id_to_otel:
                parent_otel = span_id_to_otel[span.parent_span_id]

            otel_span = self.export_span(span, parent_otel_span=parent_otel)
            if otel_span is not None:
                span_id_to_otel[span.span_id] = otel_span
                otel_spans.append(otel_span)

        return otel_spans

    def export_traces(self, traces: list[Trace]) -> int:
        """Export multiple traces. Returns count of exported spans."""
        total = 0
        for trace in traces:
            total += len(self.export_trace(trace))
        return total


# ---------------------------------------------------------------------------
# Attribute builder
# ---------------------------------------------------------------------------


def _build_otel_attributes(span: Span) -> dict[str, Any]:
    """Build OTel-compatible attribute dict from a Span."""
    attrs: dict[str, Any] = {
        "forge_agent.span_id": span.span_id,
        "forge_agent.trace_id": span.trace_id,
        "forge_agent.span_type": span.span_type.value,
        "forge_agent.duration_ms": span.duration_ms,
    }
    if span.parent_span_id:
        attrs["forge_agent.parent_span_id"] = span.parent_span_id
    if span.error_message:
        attrs["forge_agent.error"] = span.error_message

    # Merge user attributes (flatten non-string values)
    for key, value in span.attributes.items():
        if isinstance(value, (str, int, float, bool)):
            attrs[key] = value
        else:
            attrs[key] = str(value)

    return attrs


# ---------------------------------------------------------------------------
# TraceManager integration — auto-export on end_trace
# ---------------------------------------------------------------------------

_installed_exporter: OTelExporter | None = None
_original_end_trace: Any = None


def install_otel_exporter(
    service_name: str = "forge-agent",
    tracer_provider: Any | None = None,
    manager: TraceManager | None = None,
) -> OTelExporter:
    """Install an OTelExporter on the TraceManager.

    After installation, every call to ``manager.end_trace()`` will
    automatically export all spans to the configured OTel backend.

    Returns the created exporter.
    """
    global _installed_exporter, _original_end_trace

    exporter = OTelExporter(
        service_name=service_name,
        tracer_provider=tracer_provider,
    )

    mgr = manager or get_trace_manager()

    # Monkey-patch end_trace to auto-export
    _original_end_trace = mgr.end_trace

    def _patched_end_trace(trace_id: str | None = None) -> Trace | None:
        trace = _original_end_trace(trace_id)
        if trace is not None:
            try:
                exporter.export_trace(trace)
            except Exception:  # pragma: no cover
                log.warning("OTel export failed for trace %s", trace.trace_id, exc_info=True)
        return trace

    mgr.end_trace = _patched_end_trace  # type: ignore[assignment]
    _installed_exporter = exporter
    log.info("OTel exporter installed (service=%s)", service_name)
    return exporter


def uninstall_otel_exporter(manager: TraceManager | None = None) -> None:
    """Remove the OTel auto-export hook from the TraceManager."""
    global _installed_exporter, _original_end_trace

    if _original_end_trace is not None:
        mgr = manager or get_trace_manager()
        mgr.end_trace = _original_end_trace  # type: ignore[assignment]
        _original_end_trace = None

    _installed_exporter = None
    log.info("OTel exporter uninstalled")


def get_installed_exporter() -> OTelExporter | None:
    """Return the currently installed OTelExporter, or None."""
    return _installed_exporter
