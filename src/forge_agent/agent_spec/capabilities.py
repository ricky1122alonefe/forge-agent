"""Optional agent capabilities for YAML-configured agents (AGENT_PLAN A9.4)."""

from __future__ import annotations

from typing import Any

from forge_agent.agent_spec.models import AgentSpec

MEMORY_KEYWORDS = ["记住", "历史", "上次", "对比上次", "memory", "remember", "留存"]
CONSTRAINT_KEYWORDS = [
    "合规",
    "敏感",
    "黑名单",
    "白名单",
    "违规",
    "compliance",
    "禁止",
    "审核",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k in text or k in lower for k in keywords)


def detect_capabilities(requirement: str) -> list[str]:
    """Return capability names suggested by requirement text (memory default off)."""
    caps: list[str] = []
    if _contains_any(requirement, MEMORY_KEYWORDS):
        caps.append("memory")
    if _contains_any(requirement, CONSTRAINT_KEYWORDS):
        caps.append("constraints")
    return caps


def build_memory_config(agent_id: str) -> dict[str, Any]:
    return {"backend": "file", "path": f"{agent_id}_memory.json"}


def build_constraints_config() -> dict[str, Any]:
    return {"enabled": True, "builtin": "compliance"}


def capability_config_for(agent_id: str, name: str) -> dict[str, Any]:
    """Build config fragment for a named capability."""
    if name == "memory":
        return build_memory_config(agent_id)
    if name == "constraints":
        return build_constraints_config()
    raise ValueError(f"unknown capability: {name!r}")


def merge_capabilities_into_config(
    config: dict[str, Any],
    capabilities: dict[str, Any],
    agent_id: str,
) -> None:
    """Merge declared capabilities into agent config (in-place)."""
    if capabilities.get("memory"):
        memory_cfg = capabilities["memory"]
        config["memory"] = (
            memory_cfg if isinstance(memory_cfg, dict) else build_memory_config(agent_id)
        )
    if capabilities.get("constraints"):
        constraint_cfg = capabilities["constraints"]
        config["constraints"] = (
            constraint_cfg if isinstance(constraint_cfg, dict) else build_constraints_config()
        )


def apply_requirement_capabilities(spec: AgentSpec, requirement: str) -> AgentSpec:
    """Attach detected capabilities to an AgentSpec (does not enable by default)."""
    detected = detect_capabilities(requirement)
    if not detected:
        return spec
    caps = dict(spec.capabilities)
    for name in detected:
        if name not in caps:
            caps[name] = capability_config_for(spec.agent_id, name)
    spec.capabilities = caps
    merge_capabilities_into_config(spec.config, caps, spec.agent_id)
    return spec


def merge_type_capabilities(spec: AgentSpec, type_capabilities: Any) -> AgentSpec:
    """Merge optional capabilities template from an agent_type definition."""
    if not isinstance(type_capabilities, dict) or not type_capabilities:
        return spec
    caps = dict(spec.capabilities)
    for name, cfg in type_capabilities.items():
        if cfg is False:
            caps.pop(name, None)
            continue
        if cfg is True or cfg is None:
            caps[name] = capability_config_for(spec.agent_id, str(name))
        elif isinstance(cfg, dict):
            caps[str(name)] = cfg
    spec.capabilities = caps
    merge_capabilities_into_config(spec.config, caps, spec.agent_id)
    return spec
