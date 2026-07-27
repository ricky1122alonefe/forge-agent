"""Agent CI gate — block apply when mock smoke fails (AGENT_PLAN A10.1, A13.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_agent.core.contracts import AgentReport
from forge_agent.judge import Judge
from forge_agent.spec.models import AgentSpec
from forge_agent.spec.smoke import smoke_run_spec_sync


class CIGateError(ValueError):
    """Raised when apply is blocked because smoke checks failed."""

    def __init__(self, message: str, results: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.results = results


def _judge_smoke_results(
    results: list[dict[str, Any]],
    *,
    judge_min_score: float,
) -> list[dict[str, Any]]:
    """Attach Judge scores to smoke results; return entries that fail quality gate."""
    judge = Judge()
    failures: list[dict[str, Any]] = []
    for result in results:
        report = result.get("agent_report")
        if not isinstance(report, AgentReport):
            continue
        jr = judge.judge_report(report)
        judge_dict = jr.to_dict()
        result["judge"] = judge_dict
        if jr.has_critical or jr.score < judge_min_score:
            failures.append(result)
    return failures


def run_ci_gate(
    spec: AgentSpec,
    *,
    judge_gate: bool = False,
    judge_min_score: float = 0.55,
) -> list[dict[str, Any]]:
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

    if judge_gate:
        judge_failures = _judge_smoke_results(results, judge_min_score=judge_min_score)
        if judge_failures:
            parts = []
            for r in judge_failures:
                judge = r.get("judge") or {}
                parts.append(
                    f"{spec.agent_id}/{r.get('case', '?')}: "
                    f"judge score={judge.get('score')} grade={judge.get('grade')}"
                )
            raise CIGateError(
                f"Judge CI blocked apply for {spec.agent_id!r}: " + "; ".join(parts),
                results,
            )

    for result in results:
        result.pop("agent_report", None)
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
    auto_repair: bool = True,
    judge_gate: bool = True,
) -> dict[str, Any]:
    """Write agent YAML after optional CI gate; bump revision on success (A12.2)."""
    import yaml

    from forge_agent.spec.repair import run_ci_with_repair
    from forge_agent.spec.versioning import next_revision, stamp_agent_meta
    from forge_agent.spec.writer import agent_dict_to_spec, spec_to_agent_dict
    from forge_agent.web.data import get_agent

    agents = document.get("agents", []) if isinstance(document, dict) else document
    if not isinstance(agents, list):
        raise ValueError("Agent YAML must contain an 'agents' list")

    target: dict[str, Any] | None = None
    target_idx = -1
    for i, entry in enumerate(agents):
        if isinstance(entry, dict) and entry.get("agent_id") == agent_id:
            target = entry
            target_idx = i
            break
    if target is None:
        raise ValueError(f"Agent {agent_id!r} not found in YAML")

    smoke_results: list[dict[str, Any]] = []
    repair_meta: dict[str, Any] = {}
    if ci_gate:
        spec = agent_dict_to_spec(target)
        if spec.mock_cases:
            if auto_repair:
                spec, smoke_results, repair_meta = run_ci_with_repair(
                    spec,
                    judge_gate=judge_gate,
                )
            else:
                smoke_results = run_ci_gate(spec, judge_gate=judge_gate)
            repaired_entry = spec_to_agent_dict(spec)
            repaired_entry["_meta"] = dict(target.get("_meta") or {})
            repaired_entry["_meta"].update(repaired_entry.get("_meta") or {})
            agents[target_idx] = repaired_entry
            target = repaired_entry

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
        "repair_meta": repair_meta,
        "judge_gate": judge_gate,
    }
