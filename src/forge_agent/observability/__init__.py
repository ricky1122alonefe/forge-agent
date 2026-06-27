"""Observability: structured logging, tracing, metrics, event bus."""

from __future__ import annotations

from forge_agent.observability.events import EventBus
from forge_agent.observability.logger import (
    StructLogger,
    bind_context,
    clear_context,
    configure_logging,
    current_config,
    current_context,
    get_logger,
    is_configured,
    unbind_context,
)
from forge_agent.observability.metrics import MetricsCollector
from forge_agent.observability.trace import (
    Span,
    SpanStatus,
    SpanType,
    Trace,
    TraceManager,
    get_trace_manager,
    reset_trace_manager,
)

__all__ = [
    # Event bus & metrics
    "EventBus", "MetricsCollector",
    # Logger
    "StructLogger", "configure_logging", "get_logger",
    "is_configured", "current_config",
    # Context helpers
    "bind_context", "unbind_context", "clear_context", "current_context",
    # Trace
    "Span", "SpanStatus", "SpanType", "Trace", "TraceManager",
    "get_trace_manager", "reset_trace_manager",
]
