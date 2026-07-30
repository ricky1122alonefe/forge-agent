"""Trace runtime — extracted from BaseAgent (S6.1).

Manages trace spans and log-context binding during the agent run cycle.
Keeps BaseAgent thin: the observability plumbing lives here, not in
core/base.py.

BaseAgent.run() calls:
  - bind_run_context()  before the cycle starts
  - run_step_traced()   for each lifecycle step
  - unbind_run_context()  after the cycle ends
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forge_agent.core.base import BaseAgent
    from forge_agent.core.context import AgentContext


def bind_run_context(agent_id: str, domain: str, version: str, run_id: str) -> None:
    """Bind agent + run fields to log contextvars for structured logging."""
    from forge_agent.observability.logger import bind_context

    bind_context(
        agent_id=agent_id,
        domain=domain,
        agent_version=version,
        run_id=run_id,
    )


def unbind_run_context() -> None:
    """Clear the per-run log context key (keeps agent_id/domain)."""
    from forge_agent.observability.logger import unbind_context

    unbind_context("run_id")


def bind_agent_context(agent_id: str, domain: str, version: str) -> None:
    """Bind agent fields to log contextvars (used in init/shutdown)."""
    from forge_agent.observability.logger import bind_context

    bind_context(agent_id=agent_id, domain=domain, agent_version=version)


def unbind_agent_context() -> None:
    """Clear agent log context keys."""
    from forge_agent.observability.logger import unbind_context

    unbind_context("agent_id", "domain", "agent_version", "run_id")


def start_agent_span(agent_id: str, run_id: str) -> tuple[Any, Any]:
    """Start the top-level agent run span. Returns (span, trace)."""
    from forge_agent.observability.trace import SpanType, get_trace_manager

    tm = get_trace_manager()
    trace = tm.current_trace
    span = tm.start_span(
        name=f"{agent_id}.run",
        span_type=SpanType.AGENT,
        trace=trace,
        attributes={"agent_id": agent_id, "run_id": run_id},
    )
    return span, trace


def end_span(span: Any, *, status: str = "ok", error: str = "") -> None:
    """End a trace span."""
    from forge_agent.observability.trace import get_trace_manager

    tm = get_trace_manager()
    if error:
        tm.end_span(span, status="error", error_message=error)
    else:
        tm.end_span(span, status=status)


async def run_step_traced(
    agent: BaseAgent,
    step_name: str,
    ctx: AgentContext,
    trace: Any,
    **kwargs: Any,
) -> Any:
    """Execute a single lifecycle step with trace span recording."""
    from forge_agent.observability.trace import get_trace_manager

    tm = get_trace_manager()
    span_type = _step_span_type(step_name)
    span = tm.start_span(
        name=f"{agent.agent_id}.{step_name}",
        span_type=span_type,
        trace=trace,
        attributes={"step": step_name},
    )
    try:
        result = await _dispatch_step(agent, step_name, ctx, kwargs)
        tm.end_span(span, status="ok")
        return result
    except Exception as exc:
        tm.end_span(span, status="error", error_message=str(exc))
        raise


def _step_span_type(step_name: str) -> Any:
    from forge_agent.observability.trace import SpanType

    mapping = {
        "observe": SpanType.OBSERVE,
        "decide": SpanType.DECIDE,
        "act": SpanType.ACT,
        "reflect": SpanType.REFLECT,
        "learn": SpanType.LEARN,
    }
    return mapping.get(step_name, SpanType.AGENT)


async def _dispatch_step(
    agent: BaseAgent, step_name: str, ctx: AgentContext, kwargs: dict[str, Any]
) -> Any:
    """Dispatch to the correct lifecycle method."""
    if step_name == "observe":
        return await agent.observe(ctx)
    if step_name == "decide":
        return await agent.decide(ctx, kwargs["observation"])
    if step_name == "act":
        return await agent.act(ctx, kwargs["decision"])
    if step_name == "reflect":
        return await agent.reflect(ctx, kwargs["observation"], kwargs["decision"], kwargs["result"])
    if step_name == "learn":
        return await agent.learn(ctx, kwargs["observation"], kwargs["decision"], kwargs["result"])
    return None
