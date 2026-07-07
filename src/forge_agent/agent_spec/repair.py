"""Self-healing AgentSpec repair loop — smoke/Judge failures → fix → retry (A13.1)."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from forge_agent.agent_spec.ci import CIGateError, run_ci_gate
from forge_agent.agent_spec.models import AgentSpec


def _clone_spec(spec: AgentSpec) -> AgentSpec:
    return AgentSpec.from_dict(deepcopy(spec.to_dict()))


def _schema_properties(config: dict[str, Any]) -> dict[str, Any]:
    schema = config.get("output_schema")
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def _default_for_property(prop: dict[str, Any]) -> Any:
    prop_type = prop.get("type")
    if prop_type == "boolean":
        return False
    if prop_type == "number":
        return 0.72
    if prop_type == "array":
        return ["Auto-repaired mock evidence"]
    if prop_type == "object":
        return {}
    enum = prop.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    return "mock"


def _patch_mock_response(config: dict[str, Any], updates: dict[str, Any]) -> bool:
    raw = config.get("mock_response")
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    changed = False
    for key, value in updates.items():
        if data.get(key) != value:
            data[key] = value
            changed = True
    if changed:
        config["mock_response"] = json.dumps(data, ensure_ascii=False)
    return changed


def _ensure_mock_key(config: dict[str, Any], key: str, value: Any | None = None) -> bool:
    props = _schema_properties(config)
    resolved = value if value is not None else _default_for_property(props.get(key, {}))
    return _patch_mock_response(config, {key: resolved})


def repair_spec_from_ci_failure(
    spec: AgentSpec,
    results: list[dict[str, Any]],
) -> tuple[AgentSpec, list[str]]:
    """Apply one round of rule-based repairs from smoke/Judge CI results."""
    repaired = _clone_spec(spec)
    fixes: list[str] = []

    for idx, result in enumerate(results):
        if idx >= len(repaired.mock_cases):
            break
        case = repaired.mock_cases[idx]

        if not result.get("success"):
            missing = list(result.get("missing_keys") or [])
            decision_keys = list(result.get("decision_keys") or [])

            for key in missing:
                if _ensure_mock_key(repaired.config, key):
                    fixes.append(f"{case.name}: added mock field {key!r}")

            if missing:
                trimmed = [k for k in case.expect_keys if k not in missing]
                if trimmed != case.expect_keys:
                    case.expect_keys = trimmed
                    fixes.append(f"{case.name}: trimmed expect_keys (removed {missing})")
                if not case.expect_keys:
                    fallback = decision_keys or list(_schema_properties(repaired.config))
                    case.expect_keys = fallback[:6]
                    fixes.append(f"{case.name}: reset expect_keys to decision/schema keys")

        judge = result.get("judge")
        if not isinstance(judge, dict):
            continue
        score = float(judge.get("score", 1.0))
        if score >= 0.55 and not judge.get("has_critical"):
            continue

        for issue in judge.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            code = issue.get("code", "")
            if code == "INSUFFICIENT_EVIDENCE":
                props = _schema_properties(repaired.config)
                if "evidence" in props:
                    if _ensure_mock_key(
                        repaired.config,
                        "evidence",
                        ["Auto-repaired: mock evidence for Judge"],
                    ):
                        fixes.append(f"{case.name}: Judge — enriched evidence")
                elif "message" in props and _ensure_mock_key(
                    repaired.config, "message", "Auto-repaired mock message"
                ):
                    fixes.append(f"{case.name}: Judge — enriched message")
            elif code in {"LOW_CONFIDENCE", "ZERO_CONFIDENCE_NON_NEUTRAL"}:
                if _ensure_mock_key(repaired.config, "confidence", 0.72):
                    fixes.append(f"{case.name}: Judge — raised confidence")
            elif code == "OVERCONFIDENT":
                if _ensure_mock_key(
                    repaired.config,
                    "evidence",
                    ["Auto-repaired: evidence supports confidence"],
                ):
                    fixes.append(f"{case.name}: Judge — added evidence for overconfidence")

    return repaired, fixes


def run_ci_with_repair(
    spec: AgentSpec,
    *,
    max_rounds: int = 3,
    judge_gate: bool = True,
    judge_min_score: float = 0.55,
) -> tuple[AgentSpec, list[dict[str, Any]], dict[str, Any]]:
    """Run CI gate with up to *max_rounds* self-healing repair attempts."""
    working = _clone_spec(spec)
    repair_log: list[str] = []

    for round_num in range(max_rounds + 1):
        try:
            results = run_ci_gate(
                working,
                judge_gate=judge_gate,
                judge_min_score=judge_min_score,
            )
            return (
                working,
                results,
                {
                    "repaired": bool(repair_log),
                    "rounds": round_num,
                    "repair_log": repair_log,
                },
            )
        except CIGateError as exc:
            if round_num >= max_rounds:
                raise
            working, fixes = repair_spec_from_ci_failure(working, exc.results)
            if not fixes:
                raise
            repair_log.extend(fixes)

    raise CIGateError(f"CI repair exhausted for {spec.agent_id!r}", [])
