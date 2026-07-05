"""Agent asset versioning (AGENT_PLAN A8.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

AGENT_ASSET_SPEC_VERSION = 1


def next_revision(existing_agent: dict[str, Any] | None) -> int:
    """Return the next revision number for an agent YAML entry."""
    if existing_agent is None:
        return 1
    meta = existing_agent.get("_meta") or {}
    try:
        return int(meta.get("revision", 0)) + 1
    except (TypeError, ValueError):
        return 1


def stamp_agent_meta(
    meta: dict[str, Any],
    *,
    revision: int,
    reset_verification: bool = False,
) -> dict[str, Any]:
    """Attach spec_version / revision / generated_at to agent _meta."""
    stamped = dict(meta)
    stamped["spec_version"] = AGENT_ASSET_SPEC_VERSION
    stamped["revision"] = revision
    stamped["generated_at"] = datetime.now(timezone.utc).isoformat()
    if reset_verification:
        stamped.pop("smoke_verified", None)
        stamped.pop("real_run_verified", None)
        stamped["maturity"] = "draft"
    return stamped


def validate_agent_asset(agent: dict[str, Any]) -> list[str]:
    """Validate a stored agent dict meets AgentSpec asset requirements."""
    errors: list[str] = []
    meta = agent.get("_meta") if isinstance(agent.get("_meta"), dict) else {}
    spec_version = meta.get("spec_version")
    if spec_version is None:
        errors.append("missing _meta.spec_version")
    else:
        try:
            if int(spec_version) > AGENT_ASSET_SPEC_VERSION:
                errors.append(f"unsupported _meta.spec_version: {spec_version}")
        except (TypeError, ValueError):
            errors.append(f"invalid _meta.spec_version: {spec_version!r}")
    if not meta.get("primitive"):
        errors.append("missing _meta.primitive")
    mock_cases = agent.get("mock_cases")
    if not isinstance(mock_cases, list) or not mock_cases:
        errors.append("missing mock_cases")
    config = agent.get("config") if isinstance(agent.get("config"), dict) else {}
    if not config.get("output_schema"):
        errors.append("missing config.output_schema")
    return errors
