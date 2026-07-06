"""Agent CI gate — block apply when mock smoke fails (AGENT_PLAN A10.1)."""

from __future__ import annotations

from pathlib import Path
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


def persist_agent_document_with_ci(
    project_root: Path,
    agent_id: str,
    document: dict[str, Any],
    *,
    ci_gate: bool = True,
) -> dict[str, Any]:
    """Write agent YAML after optional CI gate; bump revision on success (A12.2)."""
    import yaml

    from forge_agent.agent_spec.versioning import next_revision, stamp_agent_meta
    from forge_agent.agent_spec.writer import agent_dict_to_spec
    from forge_agent.web.data import get_agent

    agents = document.get("agents", []) if isinstance(document, dict) else document
    if not isinstance(agents, list):
        raise ValueError("Agent YAML must contain an 'agents' list")

    target: dict[str, Any] | None = None
    for entry in agents:
        if isinstance(entry, dict) and entry.get("agent_id") == agent_id:
            target = entry
            break
    if target is None:
        raise ValueError(f"Agent {agent_id!r} not found in YAML")

    smoke_results: list[dict[str, Any]] = []
    if ci_gate:
        spec = agent_dict_to_spec(target)
        if spec.mock_cases:
            smoke_results = run_ci_gate(spec)

    existing = get_agent(project_root, agent_id)
    meta = stamp_agent_meta(
        dict(target.get("_meta") or {}),
        revision=next_revision(existing),
        reset_verification=True,
    )
    target["_meta"] = meta

    path = project_root / "agents" / f"{agent_id}.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {
        "success": True,
        "agent_id": agent_id,
        "revision": meta["revision"],
        "ci_gate": ci_gate,
        "smoke_results": smoke_results,
    }
