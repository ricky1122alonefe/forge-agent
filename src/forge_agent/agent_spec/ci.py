"""Agent CI gate — block apply when mock smoke fails (AGENT_PLAN A10.1)."""

from __future__ import annotations

from typing import Any

from forge_agent.agent_spec.models import AgentSpec
from forge_agent.agent_spec.smoke import smoke_run_spec_sync


class CIGateError(ValueError):
    """Raised when apply is blocked because smoke checks failed."""

    def __init__(self, message: str, results: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.results = results


def run_ci_gate(spec: AgentSpec) -> list[dict[str, Any]]:
    """Run all mock_cases smoke tests synchronously. Raises CIGateError on failure."""
    if not spec.mock_cases:
        return []

    results = smoke_all_cases_sync(spec)
    failures = [r for r in results if not r.get("success")]
    if failures:
        parts = [
            f"{spec.agent_id}/{r.get('case', '?')}: missing {r.get('missing_keys', [])}"
            for r in failures
        ]
        raise CIGateError(
            f"CI gate blocked apply for {spec.agent_id!r}: " + "; ".join(parts),
            results,
        )
    return results


def smoke_all_cases_sync(spec: AgentSpec) -> list[dict[str, Any]]:
    """Run every mock case without asyncio (for writer.apply_spec)."""
    results: list[dict[str, Any]] = []
    for idx in range(len(spec.mock_cases)):
        results.append(smoke_run_spec_sync(spec, case_index=idx))
    return results
