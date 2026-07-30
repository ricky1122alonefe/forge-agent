"""Constraint runtime — extracted from BaseAgent (S6.2).

Checks agent output against a constraint engine and blocks violations.
Keeps BaseAgent thin: the policy logic lives here, not in core/base.py.
"""

from __future__ import annotations

from typing import Any, Protocol

from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict


class _LogFn(Protocol):
    def __call__(self, level: str, msg: str, **extra: Any) -> None: ...


async def apply_constraints(
    *,
    agent_id: str,
    domain: str,
    ctx: AgentContext,
    result: AgentReport,
    engine: Any | None,
    log_fn: _LogFn,
) -> AgentReport:
    """Check ``result`` against ``engine``; block on violation.

    If ``engine`` is None, returns ``result`` unchanged.
    On violation, rewrites the report to a blocked state (RISK/0.0 confidence)
    and attaches violation details in ``constraint_result``.
    """
    if engine is None:
        return result

    text_parts = [
        *result.evidence,
        *result.warnings,
        str(result.recommended_action.value),
    ]
    text = " ".join(text_parts)

    try:
        check = await engine.check_output(
            text,
            metadata={
                "agent_id": agent_id,
                "run_id": ctx.run_id,
                "scope_id": ctx.scope_id,
                "domain": domain,
            },
        )
    except Exception as exc:
        log_fn("warning", f"constraint check failed: {exc}")
        return result

    result.constraint_result = check.to_dict()

    if not check.allowed:
        log_fn(
            "warning",
            f"Constraint violation(s) blocked output: {[v.policy_id for v in check.violations]}",
        )
        result.verdict = Verdict.RISK
        result.risk = 1.0
        result.confidence = 0.0
        result.recommended_action = Action.WATCH
        result.warnings.append(
            "Output blocked by policy: "
            + ", ".join(
                f"{v.policy_id} ({v.severity}) matched '{v.matched_text}'" for v in check.violations
            )
        )

    return result
